#!/bin/bash

# SETUP SCRIPT FOR RASPBERRY PI (MBA AUTOMATION)
# This script installs the app and configures an SSH Tunnel to your VPS.

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo ./SETUP-RASPI.sh)"
  exit
fi

echo "========================================="
echo "   MBA AUTOMATION - RASPBERRY PI SETUP   "
echo "========================================="

# 1. Update System & Install Dependencies
echo "Step 1: Updating System..."
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git autossh sshpass nano

# 2. Setup Project
echo "Step 2: Installing Application..."
USER_HOME=$(eval echo ~${SUDO_USER})
APP_DIR="$USER_HOME/mba-automation"

if [ ! -d "$APP_DIR" ]; then
    sudo -u $SUDO_USER git clone https://github.com/ibradan/mba-automation.git $APP_DIR
else
    cd $APP_DIR
    sudo -u $SUDO_USER git pull origin main
fi

cd $APP_DIR

# Setup Python Venv
if [ ! -d "venv" ]; then
    sudo -u $SUDO_USER python3 -m venv venv
fi

# Install Python Req
sudo -u $SUDO_USER ./venv/bin/pip install -r requirements.txt
sudo -u $SUDO_USER ./venv/bin/pip install gunicorn

# Install Playwright Browsers
echo "Installing Playwright Browsers..."
sudo -u $SUDO_USER ./venv/bin/playwright install chromium
sudo -u $SUDO_USER ./venv/bin/playwright install-deps

# 3. Create Systemd Service for App
echo "Step 3: Creating App Service..."
cat <<EOF > /etc/systemd/system/mba-app.service
[Unit]
Description=MBA Automation Web App
After=network.target

[Service]
User=$SUDO_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/gunicorn --workers 4 --bind 0.0.0.0:5000 webapp:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable mba-app
systemctl restart mba-app

# 4. Setup SSH Tunneling
echo "Step 4: Setting up SSH Tunnel to VPS..."
read -p "Masukkan IP VPS Anda: " VPS_IP
read -p "Masukkan User VPS (biasanya root): " VPS_USER
echo "Pastikan Anda sudah setup SSH Key agar tidak perlu password, atau install sshpass."

# Generate SSH Key if not exists
if [ ! -f "$USER_HOME/.ssh/id_rsa" ]; then
    sudo -u $SUDO_USER ssh-keygen -t rsa -N "" -f "$USER_HOME/.ssh/id_rsa"
    echo "SSH Key generated. Copying to VPS..."
    sudo -u $SUDO_USER ssh-copy-id $VPS_USER@$VPS_IP
fi

# Create Tunnel Service
cat <<EOF > /etc/systemd/system/mba-tunnel.service
[Unit]
Description=SSH Tunnel to VPS (Expose Port 5000)
After=network-online.target
Wants=network-online.target

[Service]
User=$SUDO_USER
# Force wait for WiFi/Network to settle
ExecStartPre=/bin/sleep 30
ExecStart=/usr/bin/autossh -M 0 -o "ServerAliveInterval 30" -o "ServerAliveCountMax 3" -N -R 5000:localhost:5000 ${VPS_USER}@${VPS_IP}
Restart=always
RestartSec=30
StartLimitIntervalSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable mba-tunnel
systemctl restart mba-tunnel

echo "========================================="
echo "             SETUP COMPLETE!             "
echo "========================================="
echo "1. Aplikasi jalan di Raspi (Port 5000)"
echo "2. Tunnel ke VPS aktif"
echo "   Akses dari internet: http://$VPS_IP:5000"
echo "========================================="
