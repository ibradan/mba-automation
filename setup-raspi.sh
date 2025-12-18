#!/bin/bash
# setup-raspi.sh - One-time setup script for Raspberry Pi Zero 2 W
# Use this to configure SWAP and install dependencies.

set -e

echo "🚀 Starting Raspberry Pi Zero 2 W Setup..."

# 1. OPTIMIZE SWAP (Critical for 512MB RAM)
echo "📦 Configuring Swap Memory (2GB)..."
if grep -q "CONF_SWAPSIZE=100" /etc/dphys-swapfile; then
    echo "Expanding swap from 100MB to 2048MB..."
    sudo sed -i 's/CONF_SWAPSIZE=100/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
    sudo /etc/init.d/dphys-swapfile stop
    sudo /etc/init.d/dphys-swapfile start
    echo "✅ Swap expanded."
else
    echo "ℹ️ Swap configuration already modified or not found. Skipping auto-edit."
fi

# 2. SYSTEM DEPENDENCIES
echo "🛠️ Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv libgstreamer-gl1.0-0 \
    libgstreamer-plugins-bad1.0-0 gstreamer1.0-plugins-good \
    gstreamer1.0-libav

# 3. PYTHON ENVIRONMENT
echo "🐍 Setting up Python environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ Virtual environment created."
fi

source .venv/bin/activate
pip install --upgrade pip
echo "📥 Installing Python packages from requirements.txt..."
pip install -r requirements.txt

# 4. PLAYWRIGHT
echo "🎭 Installing Playwright browsers..."
pip install playwright
# Only install chromium to save space/time
playwright install chromium --with-deps

# 5. SERVICE SETUP
echo "⚙️ Configuring systemd service..."

# Get current directory as absolute path
WORK_DIR=$(pwd)
USER_NAME=$(whoami)

SERVICE_FILE="/etc/systemd/system/mba-automation.service"

# Create service file content
sudo bash -c "cat > ${SERVICE_FILE}" <<EOL
[Unit]
Description=MBA Automation Web Server
After=network.target

[Service]
User=${USER_NAME}
WorkingDirectory=${WORK_DIR}
Environment="PATH=${WORK_DIR}/.venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="MBA_HEADLESS=1"
ExecStart=${WORK_DIR}/.venv/bin/gunicorn -w 1 -b 0.0.0.0:5000 webapp:app --timeout 120
Restart=always

[Install]
WantedBy=multi-user.target
EOL

echo "✅ Service file created at ${SERVICE_FILE}"
sudo systemctl daemon-reload
sudo systemctl enable mba-automation
sudo systemctl start mba-automation

echo "🎉 Setup Complete!"
echo "➡️  You can check logs with: sudo journalctl -u mba-automation -f"
echo "➡️  Access web interface at: http://$(hostname -I | awk '{print $1}'):5000"
