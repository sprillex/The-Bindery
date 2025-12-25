#!/bin/bash

# Fast update script for testing

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

# Ask if user wants to wipe data
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

# Fix permissions if requested
echo "If you are running this script as root but the service runs as a different user (e.g., dietpi),"
echo "you should fix file ownership now."
echo "Enter the service username to chown files to (or press Enter to skip):"
read service_user

if [ -n "$service_user" ]; then
    echo "Changing ownership to $service_user..."
    chown -R "$service_user:$service_user" .
    echo "Ownership updated."
fi

# Restart service if running
echo "Restarting service..."
if systemctl is-active --quiet rachel-module-creator.service; then
    sudo systemctl restart rachel-module-creator.service
    echo "Service restarted."
else
    echo "Service not running or not installed. If you are running this manually, please restart the server."
fi

echo "Update complete."
