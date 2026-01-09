# 🐧 Install Guide: UserLAnd (Android)

UserLAnd is a great alternative to Termux for running this application because offering a more standard Linux environment.

## 1. Setup UserLAnd
1. Open **UserLAnd** app.
2. Select **Ubuntu** (recommended) or **Debian**.
3. Choose **Terminal** connection type (SSH is fine too).
4. Wait for the session to start and log in.

## 2. Update & Install System Dependencies
Run these commands one by one:

```bash
# Update package lists
sudo apt update && sudo apt upgrade -y

# Install Python, Git, and system libraries for Playwright
sudo apt install -y python3 python3-pip python3-venv git nano \
    libevent-2.1-7 libopus0 libwoff1 libharfbuzz-icu0 gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good gstreamer1.0-libav libflite1 libavif15 \
    libenchant-2-2 libsecret-1-0 libhyphen0 libmanette-0.2-0 libgles2
```

## 3. Clone Repository
```bash
# Clone the project (latest version with optimizations)
git clone https://github.com/ibradan/mba-automation-workspace.git
cd mba-automation-workspace
```

## 4. Setup Python Environment
```bash
# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip3 install -r requirements.txt
```

## 5. Install Playwright Browsers
This is the critical step that usually fails in plain Termux.

```bash
# Install Chromium browser
playwright install chromium

# Install system dependencies for Playwright
playwright install-deps
```

## 6. Configure Settings
```bash
# Copy example settings
cp settings.json.example settings.json

# Edit settings (add your Telegram token etc)
nano settings.json
```
*Press `Ctrl+X`, then `Y`, then `Enter` to save and exit nano.*

## 7. Run the App! 🚀
```bash
python3 webapp.py
```

## 8. Access the Web Interface
UserLAnd usually shares the IP with the phone.
1. Find your phone's IP address (e.g., in Wifi Settings).
2. Open Chrome on Android.
3. Go to: `http://<PHONE-IP>:5000` (e.g., `http://192.168.1.5:5000`)
