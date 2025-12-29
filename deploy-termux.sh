#!/bin/bash
# deploy-termux.sh - Deploy to Android Termux

# Default configuration (Change these!)
TERMUX_IP="${1}"
TERMUX_USER="u0_a186"            # Usually user ID, but often just needs valid SSH key
TERMUX_PORT="8022"               # Default Termux SSH port

if [ -z "$TERMUX_IP" ]; then
    echo "⚠️  Please provide Termux IP address."
    echo "Usage: ./deploy-termux.sh <IP_ADDRESS>"
    exit 1
fi

# Path in Termux (based on user's prompt: /data/data/com.termux/files/home/projects/mba-automation)
REMOTE_PATH="/data/data/com.termux/files/home/projects/mba-automation"

echo "🚀 Deploying to Termux at ${TERMUX_IP}:${TERMUX_PORT}..."

# Copy files
echo "📤 Copying files..."
scp -r -P ${TERMUX_PORT} \
    requirements.txt \
    requirements-termux.txt \
    setup-termux.sh \
    setup-proot.sh \
    start.sh \
    webapp.py \
    mba_automation \
    templates \
    static \
    utils \
    "${TERMUX_IP}:${REMOTE_PATH}/"


echo "✅ File copy complete."
echo "📱 To start the app in Termux, run:"
echo "👉 bash start.sh"
