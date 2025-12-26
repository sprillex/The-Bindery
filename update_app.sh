#!/bin/bash

# Fast update script for testing

# Configuration Flags
SKIP_RESET=true       # Set to true to skip the data wipe prompt (defaults to Retain Data)
SKIP_PERMISSIONS=false # Set to true to skip the permission fix prompt (defaults to Skip)

echo "Checking for updates..."

# Fetch remote branches
git fetch

# Count number of remote branches (excluding HEAD)
branch_count=$(git branch -r | grep -v HEAD | wc -l)

if [ "$branch_count" -eq 1 ]; then
    # Only one branch, update to it
    branch=$(git branch -r | grep -v HEAD | sed 's/origin\///' | tr -d ' ')
    echo "Updating to branch: $branch"
    git checkout "$branch"
    git pull origin "$branch"
else
    # Multiple branches, ask user
    echo "Multiple branches found:"
    git branch -r | grep -v HEAD | nl

    echo "Enter the number of the branch you want to update to:"
    read branch_num

    # Get the branch name based on selection
    branch=$(git branch -r | grep -v HEAD | sed -n "${branch_num}p" | sed 's/origin\///' | tr -d ' ')

    if [ -z "$branch" ]; then
        echo "Invalid selection."
        exit 1
    fi

    echo "Updating to branch: $branch"
    git checkout "$branch"
    git pull origin "$branch"
fi

# Install dependencies
if [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment and installing dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt
else
    echo "No virtual environment found. Installing dependencies globally (may require root)..."
    pip install -r requirements.txt
fi

# Ask if user wants to wipe data
if [ "$SKIP_RESET" = "true" ]; then
    echo "Skipping data wipe check (defaulting to Retain Data)."
else
    echo "Do you want to wipe all data (downloads and modules)? [default: No]"
    echo "Type 'reset' to confirm wipe, or press Enter to retain data."
    read wipe_choice

    if [ "$wipe_choice" = "reset" ]; then
        echo "Wiping data..."
        rm -rf downloads/ modules/
        echo "Data wiped."
    else
        echo "Retaining data."
    fi
fi

# Fix permissions if requested
if [ "$SKIP_PERMISSIONS" = "true" ]; then
    echo "Skipping permission fix check."
else
    echo "If you are running this script as root but the service runs as a different user (e.g., dietpi),"
    echo "you should fix file ownership now."
    echo "Enter the service username to chown files to (or press Enter to skip):"
    read service_user

    if [ -n "$service_user" ]; then
        echo "Changing ownership to $service_user..."
        chown -R "$service_user:$service_user" .
        echo "Ownership updated."
    fi
fi

# Restart service
echo "Attempting to restart service..."
# Use 2>/dev/null to suppress "Failed to connect to bus" errors if systemd is not present/accessible
if systemctl list-units --type=service >/dev/null 2>&1; then
    sudo systemctl restart rachel-module-creator.service
    echo "Service restarted. Waiting 7 seconds to verify stability..."
    sleep 7

    if systemctl is-active --quiet rachel-module-creator.service; then
        echo "Service is actively running."
        systemctl status rachel-module-creator.service --no-pager | grep "Active:"

        # Attempt to verify connectivity
        echo "Verifying connectivity..."
        ip_addr=$(hostname -I | awk '{print $1}')
        if [ -z "$ip_addr" ]; then ip_addr="127.0.0.1"; fi
        port=5002
        url="https://$ip_addr:$port"

        if curl -k --output /dev/null --silent --head --fail "$url"; then
            echo "SUCCESS: Server is reachable at $url"
        else
            echo "WARNING: Service is active but failed to respond to ping at $url"
            echo "Please check if the port $port is blocked or if the application is still initializing."
        fi
    else
        echo " [31mERROR: Service failed to start or crashed immediately. [0m"
        systemctl status rachel-module-creator.service --no-pager -n 20
    fi
else
    echo "Warning: Unable to interact with systemd (systemctl). Skipping service restart."
fi

echo "Update complete."
