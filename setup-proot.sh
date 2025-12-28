#!/bin/bash
# setup-proot.sh - Setup script for Ubuntu Proot environment

echo "🔧 Setting up MBA Automation in Ubuntu Proot..."

# 1. Update package lists
echo "📦 Updating packages..."
apt update

# 2. Install system dependencies
echo "🛠️ Installing system dependencies..."
apt install -y python3 python3-pip python3-venv chromium-browser git

# 3. Setup Virtual Environment
echo "🐍 Setting up Python virtual environment..."
if [ -d ".venv" ]; then
    echo "♻️  Removing old virtual environment..."
    rm -rf .venv
fi
python3 -m venv .venv
echo "✅ Virtual environment created."

# 4. Install Python Requirements
echo "📥 Installing Python dependencies..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Create settings.json from template if not exist
if [ ! -f "settings.json" ]; then
    if [ -f "settings.json.example" ]; then
        cp settings.json.example settings.json
        echo "✅ Settings created from template (settings.json.example)"
    else
        echo '{"headless": true, "log_level": "INFO", "telegram_token": "", "telegram_chat_id": ""}' > settings.json
        echo "✅ Default settings.json created"
    fi
else
    echo "ℹ️  settings.json already exists, skipping..."
fi

echo "🎉 Setup complete!"
echo "👉 To start the webapp, run: bash start.sh"
