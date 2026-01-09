#!/bin/bash

# MBA Automation - One Click Installer for UserLAnd
# ------------------------------------------------
# Supports: Ubuntu, Debian sessions in UserLAnd

echo "🚀 Starting MBA Automation Setup..."
echo "=================================="

# 1. Update System & Install Dependencies
echo "📦 [1/5] Updating system and installing dependencies..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git nano \
    libevent-2.1-7 libopus0 libwoff1 libharfbuzz-icu0 gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good gstreamer1.0-libav libflite1 libavif15 \
    libenchant-2-2 libsecret-1-0 libhyphen0 libmanette-0.2-0 libgles2 || {
        echo "⚠️  Some libraries failed to install (common in UserLAnd), trying to proceed..."
    }

# 2. Setup Python Environment
echo "🐍 [2/5] Setting up Python environment..."
# Install requirements directly (simpler for UserLAnd than venv/activate dance for users)
pip3 install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -r requirements.txt

# 3. Install Playwright
echo "🎭 [3/5] Installing Playwright & Browser..."
playwright install chromium
sudo playwright install-deps chromium

# 4. Setup Configuration
echo "⚙️  [4/5] Setting up configuration..."
if [ ! -f settings.json ]; then
    cp settings.json.example settings.json
    echo "✅ Created settings.json from example"
else
    echo "✅ settings.json already exists"
fi

# 5. Final Checks
echo "✨ [5/5] Setup Complete!"
echo "=================================="
echo "▶️  To run the app:"
echo "   python3 webapp.py"
echo ""
echo "📱 Access from phone: http://$(hostname -I | awk '{print $1}'):5000"
echo "=================================="

# Ask to run now
read -p "🚀 Run app now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 webapp.py
fi
