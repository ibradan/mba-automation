#!/bin/bash
# deploy-raspi.sh - Deploy to Raspberry Pi

RASPI_IP="192.168.0.192"
RASPI_USER="pi"

echo "🔍 Detecting service path on Raspberry Pi..."
# Get WorkingDirectory from systemd
REMOTE_PATH=$(ssh ${RASPI_USER}@${RASPI_IP} "sudo systemctl show -p WorkingDirectory mba-automation | cut -d= -f2")

if [ -z "$REMOTE_PATH" ]; then
    echo "⚠️  Could not detect service path. Defaulting to /home/pi/projects/mba-automation"
    REMOTE_PATH="/home/pi/projects/mba-automation"
else
    echo "✅ Found service path: ${REMOTE_PATH}"
fi

echo "� Ensuring directories exist..."
ssh ${RASPI_USER}@${RASPI_IP} "mkdir -p ${REMOTE_PATH}/templates ${REMOTE_PATH}/static/css"

echo "�📤 Copying files to Raspberry Pi (${RASPI_IP})..."

# Copy file yang berubah
scp webapp.py ${RASPI_USER}@${RASPI_IP}:${REMOTE_PATH}/webapp.py
scp templates/index.html ${RASPI_USER}@${RASPI_IP}:${REMOTE_PATH}/templates/index.html
scp templates/history.html ${RASPI_USER}@${RASPI_IP}:${REMOTE_PATH}/templates/history.html
scp static/css/style.css ${RASPI_USER}@${RASPI_IP}:${REMOTE_PATH}/static/css/style.css

echo "🔄 Restarting service..."
ssh ${RASPI_USER}@${RASPI_IP} "sudo systemctl restart mba-automation"

echo "✅ Update complete!"
echo "🌐 Access: http://${RASPI_IP}:5000"
echo ""
echo "📊 Service status:"
ssh ${RASPI_USER}@${RASPI_IP} "sudo systemctl status mba-automation --no-pager | head -10"
