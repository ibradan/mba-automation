#!/bin/bash
# deploy-raspi5.sh - Deploy Ternak Uang to Raspberry Pi 5 (ARM64)

# Color coding
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Raspberry Pi 5 Deployment for Ternak Uang...${NC}"

# 1. Update System
echo -e "${GREEN}📦 Updating system packages...${NC}"
sudo apt update && sudo apt upgrade -y

# 2. Install Dependencies
echo -e "${GREEN}🛠️ Installing Python and browser dependencies...${NC}"
sudo apt install -y python3 python3-pip python3-venv chromium-browser libgbm-dev libnss3 libatk-bridge2.0-0 libgtk-3-0

# 3. Setup Project Directory
PROJECT_DIR="$(pwd)"
echo -e "${GREEN}📂 Setting up in $PROJECT_DIR...${NC}"

# 4. Create Virtual Environment
echo -e "${GREEN}🐍 Creating virtual environment...${NC}"
python3 -m venv .venv
source .venv/bin/activate

# 5. Install Python Requirements
echo -e "${GREEN}📦 Installing Python requirements...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# 6. Install Playwright and its Chromium
echo -e "${GREEN}🎬 Installing Playwright browsers...${NC}"
playwright install chromium
# Install system dependencies for browsers
sudo playwright install-deps

# 7. Create Systemd Service
echo -e "${GREEN}⚙️ Configuring systemd service...${NC}"
SERVICE_FILE="/etc/systemd/system/ternakuang.service"
USER_NAME="$(whoami)"

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=Ternak Uang Automation Web App
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/.venv/bin/python $PROJECT_DIR/webapp.py
Restart=always
Environment=PYTHONPATH=$PROJECT_DIR
Environment=MBA_HEADLESS=true

[Install]
WantedBy=multi-user.target
EOF

# 8. Start Service
echo -e "${GREEN}🔄 Starting the service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable ternakuang
sudo systemctl restart ternakuang

echo -e "${BLUE}✅ Deployment Finished!${NC}"
echo -e "Application is running as a service."
echo -e "You can check logs with: ${BLUE}journalctl -u ternakuang -f${NC}"
echo -e "Access the UI locally at: ${BLUE}http://$(hostname -I | awk '{print $1}'):5000${NC}"
