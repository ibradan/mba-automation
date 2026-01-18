#!/bin/bash
# update.sh - Quick update script for Raspberry Pi

set -e

echo "🔄 Updating MBA Automation..."

# Pull latest from git
echo "📥 Pulling from Git..."
git pull origin user-custom-version

# Restart the service with full stop/start cycle
echo "🔁 Stopping service..."
sudo systemctl stop mba-automation

# Kill any remaining gunicorn workers
echo "🔪 Killing stale workers..."
sudo pkill -9 gunicorn 2>/dev/null || true
sleep 2

echo "🚀 Starting service..."
sudo systemctl start mba-automation

echo "✅ Update complete!"
echo "📊 Service status:"
sudo systemctl status mba-automation --no-pager -l | head -15
