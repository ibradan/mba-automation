#!/bin/bash
# start.sh - One-click startup for MBA Automation in Termux (Proot)

# Absolute path to project
PROJECT_PATH="/data/data/com.termux/files/home/projects/mba-automation"

echo "🚀 Starting MBA Automation in Ubuntu Proot..."

# Check if proot-distro is installed
if ! command -v proot-distro &> /dev/null; then
    echo "❌ Error: proot-distro not found."
    echo "📦 Installing proot-distro..."
    pkg install -y proot-distro
    echo "📥 Installing Ubuntu..."
    proot-distro install ubuntu
    echo "✅ Ubuntu installed. Please run 'bash start.sh' again."
    exit 0
fi

# Run everything inside Ubuntu proot
proot-distro login ubuntu -- bash -c "
    cd $PROJECT_PATH || { echo '❌ Project directory not found at $PROJECT_PATH'; exit 1; }
    
    # Check if virtual environment exists
    if [ ! -d .venv ]; then
        echo '⚠️  Virtual environment not found!'
        echo '📦 Running setup first...'
        bash setup-proot.sh
    fi
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Check if Flask is installed
    if ! python3 -c 'import flask' 2>/dev/null; then
        echo '⚠️  Dependencies not installed!'
        echo '📦 Running setup first...'
        bash setup-proot.sh
        source .venv/bin/activate
    fi
    
    # Start the web app
    echo '🔥 Starting Web Application...'
    python3 webapp.py
"

