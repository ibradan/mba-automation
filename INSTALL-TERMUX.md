# 📱 MBA Automation - Panduan Instalasi (Termux)

Aplikasi automasi untuk menjalankan task harian secara otomatis di Android menggunakan Termux.

## 🚀 Instalasi Lengkap di HP Teman

### 1️⃣ Install Termux
- Download & Install **Termux** dari [F-Droid](https://f-droid.org/packages/com.termux/) atau Play Store
- Buka Termux

### 2️⃣ Setup Awal Termux
```bash
# Install semua dependencies sekaligus
pkg update && pkg upgrade -y && pkg install -y proot-distro git openssh && proot-distro install ubuntu
```

### 3️⃣ Download Aplikasi
```bash
# Buat folder projects (kalau belum ada)
mkdir -p ~/projects
cd ~/projects

# Clone repository
git clone https://github.com/ibradan/mba-automation.git
cd mba-automation
```

### 4️⃣ Setup Environment
```bash
# Setup Ubuntu Proot environment (auto-creates settings.json)
bash setup-proot.sh
```
*(Proses ini bisa 5-10 menit, sabar ya...)*

### 5️⃣ Jalankan Aplikasi
```bash
# Start server
bash start.sh
```

### 6️⃣ Akses dari Browser
1. Buka **Chrome** di HP yang sama
2. Akses: `http://localhost:5000`
3. Klik icon ⚙️ (gear) di pojok kanan atas
4. Pilih **"Install Aplikasi"**
5. Ikuti instruksi yang muncul

---

## 🔄 Update Aplikasi (Kalau Ada Versi Baru)

```bash
cd ~/projects/mba-automation
git pull
bash start.sh
```

---

## ⚙️ Konfigurasi Telegram (Opsional)

Kalau mau notifikasi Telegram:

1. Buat bot baru via [@BotFather](https://t.me/BotFather)
2. Dapatkan Chat ID via [@userinfobot](https://t.me/userinfobot)
3. Edit `settings.json`:
```json
{
    "headless": true,
    "log_level": "INFO",
    "telegram_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    "telegram_chat_id": "987654321"
}
```

---

## 🛑 Stop Aplikasi

Tekan `Ctrl+C` di Termux untuk stop server.

---

## 💡 Tips

- **Background Mode**: Install `termux-wake-lock` untuk jalan di background
  ```bash
  pkg install termux-wake-lock
  termux-wake-lock
  bash start.sh
  ```

- **Auto-Start**: Pakai Termux:Boot (perlu app tambahan dari F-Droid)

---

## 🆘 Troubleshooting

**Aplikasi tidak jalan?**
- Pastikan Ubuntu sudah diinstall: `proot-distro list`
- Cek log error di Termux
- Restart Termux dan coba lagi

**Browser tidak bisa akses?**
- Pastikan server sudah jalan (ada output di Termux)
- Gunakan Chrome (bukan browser lain)
- Coba akses via `http://127.0.0.1:5000`

---

## 📞 Bantuan

Kalau ada masalah, hubungi yang share aplikasi ini! 😊
