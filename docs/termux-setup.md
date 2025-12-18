# Termux Deployment Guide (Android) - VERIFIED ✅

Menjalankan aplikasi ini di Android via Termux ternyata sangat powerfull. Berdasarkan pengetesan, metode paling stabil adalah menggunakan **Ubuntu 24.04** di dalam **proot-distro**.

> [!IMPORTANT]
> **PENTING**: Gunakan Termux dari **F-Droid** atau [GitHub Resmi](https://github.com/termux/termux-app/releases), bukan Google Play Store!

## Langkah 1: Persiapan Host (Termux)

Buka Termux dan siapkan pintunya:
```bash
pkg update && pkg upgrade -y
pkg install openssh proot-distro -y
passwd  # Buat password SSH
sshd    # Nyalakan SSH agar bisa diremote dari Laptop
ifconfig # Catat IP HP agan
```

## Langkah 2: Instal & Setup Ubuntu

Masuk ke lingkungan Linux asli di dalam HP:
```bash
proot-distro install ubuntu
proot-distro login ubuntu
```

Begitu masuk (`root@localhost`), instal mesin utamanya:
```bash
apt update && apt upgrade -y
apt install python3 python3-pip python3-venv -y
```

## Langkah 3: Setup Project & Playwright

Masuk ke folder project yang sudah dikirim dari Laptop:
```bash
cd /data/data/com.termux/files/home/projects/mba-automation

# Buat Environment
python3 -m venv .venv
source .venv/bin/activate

# Instal Dependencies
pip install flask gunicorn python-dotenv playwright

# FIX: Instal Browser & Library Pendukung (CRITICAL)
playwright install chromium
playwright install-deps
```

## Langkah 4: Jalankan Aplikasi

```bash
# Tambahkan flag headless agar jalan di background HP
export MBA_HEADLESS=1

# Jalankan server
python3 webapp.py
```

### Tips & Troubleshooting
- **Wake Lock**: Tarik notifikasi Termux ke bawah, klik **"Acquire Wake Lock"** agar Android tidak mematikan aplikasi saat layar mati.
- **Port**: Aplikasi berjalan di `192.168.0.xxx:5000`. Pastikan HP dan Laptop di WiFi yang sama.
- **Remote Access (Data Seluler)**: Jika ingin akses dari luar rumah pakai data seluler, instal **Tailscale** di HP agan. Gunakan IP Tailscale tersebut untuk membuka dashboard.
- **Dependencies**: Jika muncul error browser, pastikan sudah menjalankan `playwright install-deps` di dalam Ubuntu.
```
