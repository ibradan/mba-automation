#!/bin/bash
# setup_tunnel.sh - Setup Persistent Reverse SSH Tunnel to VPS using Autossh
# Run this ON the Raspberry Pi

set -e

# --- CONFIGURATION (EDIT THESE) ---
VPS_USER="root"             # User di VPS
VPS_IP="YOUR_VPS_IP"        # IP Address VPS Anda
VPS_PORT="22"               # SSH Port VPS
REMOTE_PORT="8080"          # Port di VPS yang akan forward ke Raspi (Example: 8080 -> 5000)
LOCAL_PORT="5000"           # Port aplikasi di Raspi

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

# 2. Check SSH Key
if [ ! -f "$KEY_PATH" ]; then
    echo "⚠️  SSH Key not found at $KEY_PATH"
    echo "   Generating new key..."
    ssh-keygen -t rsa -b 4096 -f "$KEY_PATH" -N ""
    echo "   IMPORTANT: Copy this public key to your VPS:"
    echo "   ------------------------------------------------"
    cat "$KEY_PATH.pub"
    echo "   ------------------------------------------------"
    echo "   Run on VPS: echo 'CONTENT_ABOVE' >> ~/.ssh/authorized_keys"
    read -p "   Press Enter after you have added the key to VPS..."
fi

# 3. Create Systemd Service
echo "⚙️ Creating systemd service..."

# Autossh command:
# -M 0 : monitoring port (disabled, using echo)
# -N : Do not execute remote command
# -R : Reverse tunnel
CMD="/usr/bin/autossh -M 0 -N -o \"ServerAliveInterval 30\" -o \"ServerAliveCountMax 3\" -R $REMOTE_PORT:localhost:$LOCAL_PORT $VPS_USER@$VPS_IP -p $VPS_PORT -i $KEY_PATH"

SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

sudo bash -c "cat > $SERVICE_FILE" <<EOL
[Unit]
Description=MBA Automation Reverse Tunnel
After=network.target

[Service]
User=$(whoami)
ExecStart=$CMD
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL

echo "   ✓ Service file created at $SERVICE_FILE"

# 4. Enable info
echo "🚀 Enabling Service..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo "✅ Tunnel Setup Complete!"
echo "   Check status: sudo systemctl status $SERVICE_NAME"
