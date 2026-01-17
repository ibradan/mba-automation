#!/bin/bash
# update.sh - Quick update script for Raspberry Pi

set -e

echo "🔄 Updating MBA Automation..."

# Pull latest from git
echo "📥 Pulling from Git..."
git pull origin user-custom-version

# Restart the service
echo "🔁 Restarting service..."
sudo systemctl restart mba-automation

echo "✅ Update complete!"
echo "📊 Service status:"
sudo systemctl status mba-automation --no-pager -l | head -15
