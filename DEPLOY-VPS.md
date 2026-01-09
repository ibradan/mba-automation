# 🚀 Panduan Deploy ke VPS (Docker)

Cara termudah dan paling stabil untuk menjalankan aplikasi ini di VPS adalah menggunakan **Docker**.

## 1. Persiapan VPS
Pastikan VPS sudah terinstall Docker & Docker Compose.
Jika belum, jalankan perintah ini (untuk Ubuntu/Debian):

```bash
# Update repo
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Tambahkan user saat ini ke grup docker (agar tidak perlu sudo terus)
sudo usermod -aG docker $USER
newgrp docker
```

## 2. Upload File
Upload semua file project ini ke folder di VPS, misalnya `/home/prajurit/mba-automation`.

## 3. Jalankan Aplikasi
Masuk ke folder project, lalu jalankan:

```bash
docker compose up -d --build
```

- `--build`: Membuild image baru (perlu di awal atau jika code berubah).
- `-d`: Detached mode (berjalan di background).

## 4. Cek Status
Cek apakah container sudah berjalan:
```bash
docker compose ps
```

Cek logs jika ada masalah:
```bash
docker compose logs -f
```

## 5. Akses Web
Buka browser dan akses: `http://IP_VPS_ANDA:5000`

---

### 💡 Catatan Penting
- **Data Persisten**: File `accounts.json`, `users.json`, `settings.json`, dan folder `logs` di-mount ke luar container. Jadi jika container dihapus/restart, data akun **TIDAK HILANG**.
- **Update Codingan**:
  Jika ada update code baru (misal hasil git pull), cukup jalankan:
  ```bash
  docker compose up -d --build
  ```
