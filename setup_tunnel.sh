#!/bin/bash
# setup_tunnel.sh - Set up persistent SSH tunnel service along with app service

echo "🔧 Setting up Autossh Tunnel Service..."

# 1. Stop existing service if any
sudo systemctl stop autossh-tunnel 2>/dev/null

# 2. Kill any lingering autossh/ssh processes for port 5000
echo "🧹 Cleaning up old processes..."
sudo pkill -f "autossh.*5000:localhost:5000"
sudo pkill -f "ssh.*5000:localhost:5000"

# 3. Create Systemd Service File
echo "📝 Creating service file..."
sudo tee /etc/systemd/system/autossh-tunnel.service << 'EOF'
[Unit]
Description=AutoSSH Tunnel to VPS
After=network.target

[Service]
User=pi
# Restart every 10s if it fails
Restart=always
RestartSec=10s
# Environment variables if needed
Environment="AUTOSSH_GATETIME=0"
# Main Exec command
ExecStart=/usr/bin/autossh -M 0 -N \
    -o "ServerAliveInterval 15" \
    -o "ServerAliveCountMax 3" \
    -o "ExitOnForwardFailure yes" \
    -o "StrictHostKeyChecking=no" \
    -R 5000:localhost:5000 \
    root@202.10.36.191 -p 22 \
    -i /home/pi/.ssh/id_rsa

[Install]
WantedBy=multi-user.target
EOF

# 4. Enable and Start
echo "🚀 Starting service..."
sudo systemctl daemon-reload
sudo systemctl enable autossh-tunnel
sudo systemctl start autossh-tunnel

# 5. Check Status
echo "📊 Checking status..."
sleep 2
sudo systemctl status autossh-tunnel --no-pager

echo ""
echo "✅ Setup Complete!"
echo "If ACTIVE (running), check VPS: curl localhost:5000"
