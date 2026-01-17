#!/bin/bash

# update.sh - Quick update script
set -e

echo "🚀 Updating MBA Automation..."

# 1. Pull latest changes
echo "📥 Pulling latest code..."
git pull

# 2. Update Python dependencies (if changed)
if [ -f "requirements.txt" ]; then
    echo "📦 Checking dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt
fi

# 3. Restart Service
echo "🔄 Restarting Service..."
sudo systemctl restart mba-automation.service

echo "✅ Update Complete!"
echo "   App is running at: http://$(hostname -I | awk '{print $1}'):5000"
