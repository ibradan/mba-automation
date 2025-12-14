# Raspberry Pi Deployment Guide

Panduan untuk menjalankan MBA Automation di Raspberry Pi dengan auto-start saat boot.

## Requirements

- **Raspberry Pi 4/5** (rekomendasi: 2GB+ RAM)
- **Raspberry Pi OS** (Lite atau Desktop)
- Koneksi internet

## Quick Start (Otomatis) ⚡

Cara paling mudah - jalankan script setup otomatis:

```bash
# 1. Masuk ke directory project di Raspberry Pi
cd /home/pi/projects

# 2. Jalankan setup script
chmod +x deploy/setup-raspi.sh
./deploy/setup-raspi.sh
```

Script akan otomatis:
- ✅ Install semua system dependencies
- ✅ Buat Python virtual environment  
- ✅ Install Python packages
- ✅ Install Playwright browsers
- ✅ Setup systemd service untuk auto-start

Setelah selesai, akses web UI di: `http://<ip-raspberry-pi>:5000/`

---

## Manual Setup

Jika ingin setup manual:

### 1. SSH ke Raspberry Pi

```bash
ssh pi@raspberrypi
cd /home/pi/projects
```

### 2. Install dependencies

```bash
cd /home/pi/projects

# System packages
sudo apt update && sudo apt install -y python3 python3-pip python3-venv chromium-browser

# Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Playwright browsers
.venv/bin/python -m playwright install chromium
```

### 3. Create .env file

```bash
cat > .env <<'EOF'
FLASK_SECRET=ganti-dengan-secret-random-kamu
EOF
chmod 600 .env
```

### 4. Setup systemd service

```bash
sudo cp deploy/mba-automation.service /etc/systemd/system/
# Edit paths jika perlu: sudo nano /etc/systemd/system/mba-automation.service

sudo systemctl daemon-reload
sudo systemctl enable --now mba-automation.service
```

---

## Useful Commands

| Command | Description |
|---------|-------------|
| `sudo systemctl start mba-automation` | Start service |
| `sudo systemctl stop mba-automation` | Stop service |
| `sudo systemctl restart mba-automation` | Restart service |
| `sudo systemctl status mba-automation` | Check status |
| `sudo journalctl -u mba-automation -f` | View logs (realtime) |

---

## Troubleshooting

### Service tidak start
```bash
# Check logs
sudo journalctl -u mba-automation -n 50

# Common issues:
# - Path salah di service file
# - .env file tidak ada
# - Playwright browsers belum diinstall
```

### Chromium error
```bash
# Install dependencies yang mungkin kurang
sudo apt install -y libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2
```

### Check timezone
```bash
# Pastikan timezone sudah benar untuk schedule
timedatectl
sudo timedatectl set-timezone Asia/Jakarta
```

---

## Security Notes

- ⚠️ Jangan expose port 5000 ke internet publik tanpa authentication
- 🔒 Gunakan reverse proxy (nginx) + TLS jika perlu akses dari luar
- 🔑 Jaga file `.env` tetap private (chmod 600)
