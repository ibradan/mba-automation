#!/bin/bash
# setup_tunnel.sh - Setup Persistent Reverse SSH Tunnel to VPS using Autossh
# Run this ON the Raspberry Pi

set -e

# --- CONFIGURATION ---
VPS_USER="root"
VPS_IP="202.10.36.191"      # UPDATED with verified IP
VPS_PORT="22"

REMOTE_PORT="5000"
LOCAL_PORT="5000"

KEY_PATH="$HOME/.ssh/id_rsa"
SERVICE_NAME="mba-tunnel"

echo "🚇 Setting up Autossh Tunnel..."
echo "   Raspi :$LOCAL_PORT <==> VPS :$REMOTE_PORT"

# 1. Check/Install Autossh
if ! command -v autossh &> /dev/null; then
    echo "📦 Installing autossh..."
    sudo apt-get update
    sudo apt-get install -y autossh
else
    echo "   ✓ Autossh already installed"
fi

# 2. Key Check (Skipping generation as we verified it works)
if [ ! -f "$KEY_PATH" ]; then
    echo "⚠️  SSH Key not found at $KEY_PATH. Please generate it first."
    exit 1
fi
echo "   ✓ SSH Key found."

# 3. Create Systemd Service
echo "⚙️ Creating systemd service..."

# Autossh command:
# -M 0 : monitoring port (disabled)
# -N : Do not execute remote command
# -R : Reverse tunnel
# -o "ServerAliveInterval 30" : Keepalive
# -o "ServerAliveCountMax 3" : Keepalive
# -o "ExitOnForwardFailure yes" : Restart if port forwarding fails
# -o "StrictHostKeyChecking=no" : Avoid interactive prompts
CMD="/usr/bin/autossh -M 0 -N -o \"ServerAliveInterval 30\" -o \"ServerAliveCountMax 3\" -o \"ExitOnForwardFailure yes\" -o \"StrictHostKeyChecking=no\" -R $REMOTE_PORT:localhost:$LOCAL_PORT $VPS_USER@$VPS_IP -p $VPS_PORT -i $KEY_PATH"

SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

sudo bash -c "cat > $SERVICE_FILE" <<EOL
[Unit]
Description=MBA Automation Reverse Tunnel
After=network.target ssh.service

[Service]
User=$(whoami)
ExecStart=$CMD
Restart=always
RestartSec=10
StartLimitInterval=0

[Install]
WantedBy=multi-user.target
EOL

echo "   ✓ Service file created at $SERVICE_FILE"

# 4. Enable info
echo "🚀 Enabling and Restarting Service..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

# Wait a bit to check status
sleep 2

echo "✅ Tunnel Setup Complete!"
echo "   Check status: sudo systemctl status $SERVICE_NAME"
