#!/bin/bash
# deploy-termux.sh - Deploy to Android Termux

# Default configuration (Change these!)
TERMUX_IP="${1:-192.168.1.xxx}" # User replaces this or passes as arg
TERMUX_USER="u0_a186"            # Usually user ID, but often just needs valid SSH key
TERMUX_PORT="8022"               # Default Termux SSH port

if [ "$TERMUX_IP" == "192.168.1.xxx" ]; then
    echo "⚠️  Please provide Termux IP address."
    echo "Usage: ./deploy-termux.sh <IP_ADDRESS>"
    exit 1
fi

# Path in Termux (based on user's prompt: /data/data/com.termux/files/home/projects/mba-automation)
REMOTE_PATH="/data/data/com.termux/files/home/projects/mba-automation"

echo "🚀 Deploying to Termux at ${TERMUX_IP}:${TERMUX_PORT}..."

# Copy files
echo "📤 Copying files..."
scp -P ${TERMUX_PORT} requirements.txt "${TERMUX_IP}:${REMOTE_PATH}/requirements.txt"
scp -P ${TERMUX_PORT} -r mba_automation "${TERMUX_IP}:${REMOTE_PATH}/"
scp -P ${TERMUX_PORT} -r templates "${TERMUX_IP}:${REMOTE_PATH}/"
scp -P ${TERMUX_PORT} -r static "${TERMUX_IP}:${REMOTE_PATH}/"
scp -P ${TERMUX_PORT} -r utils "${TERMUX_IP}:${REMOTE_PATH}/"
scp -P ${TERMUX_PORT} termux_boot.sh "${TERMUX_IP}:${REMOTE_PATH}/"
scp -P ${TERMUX_PORT} webapp.py "${TERMUX_IP}:${REMOTE_PATH}/webapp.py"

echo "✅ File copy complete."
echo "⚠️  NOTE: You may need to manual restart the python script in Termux manually since there is no systemd."
echo "👉 Run in Termux: pkill -f webapp.py && python webapp.py &"
