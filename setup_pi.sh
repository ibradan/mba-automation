#!/bin/bash

# setup_pi.sh - One-click setup for Raspberry Pi
set -e

echo "🚀 Starting MBA Automation Setup for Raspberry Pi..."

# 1. Update System & Install Base Dependencies
echo "📦 Updating system and installing base dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv git

# 2. Create Virtual Environment
echo "🐍 Setting up Python Virtual Environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "   ✓ Virtual environment created."
else
    echo "   ✓ Virtual environment already exists."
fi

# Activate venv
source venv/bin/activate

# 3. Install Python Requirements
echo "📥 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Install Playwright & Browsers
echo "🎭 Installing Playwright browsers..."
playwright install chromium
echo "   Installing system dependencies for Playwright (may ask for password)..."
sudo ./venv/bin/playwright install-deps chromium 2>/dev/null || echo "   (Skipping explicit install-deps, assuming system packages are OK or handled)"

# 5. Setup Systemd Service
echo "⚙️ Configuring Systemd Service..."
SERVICE_FILE="/etc/systemd/system/mba-automation.service"
CURRENT_USER=$(whoami)
CURRENT_DIR=$(pwd)

# Create service file content
start_command="$CURRENT_DIR/venv/bin/gunicorn --workers 2 --bind 0.0.0.0:5000 webapp:app"

sudo bash -c "cat > $SERVICE_FILE" <<EOL
[Unit]
Description=MBA Automation Service
After=network.target

[Service]
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$start_command
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOL

echo "   ✓ Service file created at $SERVICE_FILE"

# 6. Enable and Start Service
echo "🚀 Starting Service..."
sudo systemctl daemon-reload
sudo systemctl enable mba-automation
sudo systemctl restart mba-automation

echo "✅ Setup Complete!"
echo "   The application is running in the background."
echo "   You can check status with: sudo systemctl status mba-automation"
echo "   View logs with: journalctl -u mba-automation -f"
