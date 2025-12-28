#!/bin/bash
# start-termux.sh - One-click startup for Ternak Uang in Termux (Ubuntu Proot)

# Path where your project is located in Termux
PROJECT_PATH="/data/data/com.termux/files/home/projects/mba-automation"

echo "🚀 Starting Ternak Uang in Ubuntu Proot..."

# 1. Check if proot-distro is installed
if ! command -v proot-distro &> /dev/null; then
    echo "❌ Error: proot-distro not found. Please install it first in Termux."
    exit 1
fi

# 2. Run the commands inside Ubuntu proot
# We use -- bash -c to execute the sequence of commands in one go
proot-distro login ubuntu -- bash -c "
    cd $PROJECT_PATH || { echo '❌ Directory not found!'; exit 1; }
    if [ -f .venv/bin/activate ]; then
        source .venv/bin/activate
        echo '✅ Virtual environment activated.'
    else
        echo '⚠️  Virtual environment (.venv) not found. Trying global python...'
    fi
    echo '🔥 Starting Web App...'
    python3 webapp.py
"
