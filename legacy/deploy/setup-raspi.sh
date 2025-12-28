#!/bin/bash
# =============================================================================
# MBA Automation - Raspberry Pi 5 Setup Script
# =============================================================================
# Script ini akan menginstall semua dependensi dan mengkonfigurasi
# aplikasi MBA Automation untuk berjalan otomatis saat boot.
#
# Cara pakai:
#   chmod +x deploy/setup-raspi.sh
#   ./deploy/setup-raspi.sh
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  MBA Automation - Raspberry Pi Setup  ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${YELLOW}Project directory: ${PROJECT_DIR}${NC}"
echo ""

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    MODEL=$(cat /proc/device-tree/model)
    echo -e "${GREEN}Detected: ${MODEL}${NC}"
else
    echo -e "${YELLOW}Warning: Not running on Raspberry Pi (or model not detected)${NC}"
    echo "Continuing anyway..."
fi
echo ""

# -----------------------------------------------------------------------------
# Step 1: Update system packages
# -----------------------------------------------------------------------------
echo -e "${GREEN}[1/7] Updating system packages...${NC}"
sudo apt update && sudo apt upgrade -y
echo ""

# -----------------------------------------------------------------------------
# Step 2: Install system dependencies
# -----------------------------------------------------------------------------
echo -e "${GREEN}[2/7] Installing system dependencies...${NC}"
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    chromium \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libnss3 \
    libnspr4 \
    libglib2.0-0 \
    git || {
        echo -e "${YELLOW}Some packages may have different names. Trying alternative...${NC}"
        sudo apt install -y python3 python3-pip python3-venv chromium git
    }
echo ""

# -----------------------------------------------------------------------------
# Step 3: Create Python virtual environment
# -----------------------------------------------------------------------------
echo -e "${GREEN}[3/7] Creating Python virtual environment...${NC}"
cd "$PROJECT_DIR"

if [ -d ".venv" ]; then
    echo "Virtual environment already exists, skipping creation..."
else
    python3 -m venv .venv
    echo "Virtual environment created at .venv/"
fi
echo ""

# -----------------------------------------------------------------------------
# Step 4: Install Python packages
# -----------------------------------------------------------------------------
echo -e "${GREEN}[4/7] Installing Python packages...${NC}"
# Use direct path to venv pip (source activate doesn't work reliably in scripts)
"${PROJECT_DIR}/.venv/bin/pip" install --upgrade pip
"${PROJECT_DIR}/.venv/bin/pip" install -r requirements.txt
echo ""

# -----------------------------------------------------------------------------
# Step 5: Install Playwright browsers
# -----------------------------------------------------------------------------
echo -e "${GREEN}[5/7] Installing Playwright browsers...${NC}"
.venv/bin/python -m playwright install chromium
echo ""

# -----------------------------------------------------------------------------
# Step 6: Create .env file if not exists
# -----------------------------------------------------------------------------
echo -e "${GREEN}[6/7] Setting up environment file...${NC}"
if [ -f ".env" ]; then
    echo ".env file already exists, skipping..."
else
    # Generate a random secret
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    cat > .env <<EOF
FLASK_SECRET=${SECRET}
# Add other environment variables here if needed
EOF
    chmod 600 .env
    echo ".env file created with random secret"
fi
echo ""

# -----------------------------------------------------------------------------
# Step 7: Setup systemd service
# -----------------------------------------------------------------------------
echo -e "${GREEN}[7/7] Setting up systemd service...${NC}"

# Get current user and group
CURRENT_USER=$(whoami)
CURRENT_GROUP=$(id -gn)

# Create a temporary service file with correct paths
TEMP_SERVICE="/tmp/mba-automation.service"
cat > "$TEMP_SERVICE" <<EOF
[Unit]
Description=MBA Automation Web UI
After=network.target

[Service]
User=${CURRENT_USER}
Group=${CURRENT_GROUP}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/.venv/bin/python webapp.py
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Copy to systemd directory
sudo cp "$TEMP_SERVICE" /etc/systemd/system/mba-automation.service
rm "$TEMP_SERVICE"

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable mba-automation.service

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}           Setup Complete!             ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Service status: ${YELLOW}mba-automation.service${NC}"
echo ""
echo "Commands yang berguna:"
echo -e "  ${YELLOW}sudo systemctl start mba-automation${NC}   - Start service"
echo -e "  ${YELLOW}sudo systemctl stop mba-automation${NC}    - Stop service"
echo -e "  ${YELLOW}sudo systemctl restart mba-automation${NC} - Restart service"
echo -e "  ${YELLOW}sudo systemctl status mba-automation${NC}  - Check status"
echo -e "  ${YELLOW}sudo journalctl -u mba-automation -f${NC}  - View logs"
echo ""

# Get IP address
IP_ADDR=$(hostname -I | awk '{print $1}')
echo -e "Web UI akan tersedia di: ${GREEN}http://${IP_ADDR}:5000/${NC}"
echo ""

# Ask if user wants to start the service now
read -p "Mau start service sekarang? (y/n): " START_NOW
if [ "$START_NOW" = "y" ] || [ "$START_NOW" = "Y" ]; then
    sudo systemctl start mba-automation.service
    echo ""
    sudo systemctl status mba-automation.service --no-pager
    echo ""
    echo -e "${GREEN}Service started! Buka browser dan akses http://${IP_ADDR}:5000/${NC}"
else
    echo ""
    echo "OK, service tidak di-start. Jalankan 'sudo systemctl start mba-automation' kapan saja."
fi
