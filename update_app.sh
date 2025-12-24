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

echo "Update complete."
