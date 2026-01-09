# SETUP CLOUDFLARE TUNNEL (GRATIS & AMAN)

Ini adalah cara paling **MODERN & GRATIS** untuk mengonlinekan Raspberry Pi (atau laptop/PC rumah) tanpa perlu VPS, tanpa perlu setting port forwarding modem, dan otomatis HTTPS.

Syarat:
1.  Punya Akun Cloudflare (Gratis).
2.  Punya Nama Domain (Bisa beli murah .com/.my.id) yang sudah connect ke Cloudflare.

## LANGKAH 1: Setup di Raspberry Pi

### 1. Install Cloudflared
Masuk ke terminal Raspi dan jalankan:

```bash
# Tambahkan repository Cloudflare
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb

# Install
sudo dpkg -i cloudflared.deb
```
*(Catatan: Jika pakai Raspi model lama (32-bit), ganti `arm64` dengan `armhf`)*.

### 2. Login ke Cloudflare
```bash
cloudflared tunnel login
```
Lalu copy link yang muncul, buka di browser HP/Laptop, pilih domain yang mau dipakai, dan Authorize.

### 3. Buat Tunnel
Kita namakan tunnelnya "mba-app".
```bash
cloudflared tunnel create mba-app
```
Simpan **Tunnel ID** yang muncul (kode panjang UUID).

### 4. Konfigurasi Tunnel
Buat file config:
```bash
mkdir -p ~/.cloudflared
nano ~/.cloudflared/config.yml
```

Isi dengan (Ganti `<Tunnel-UUID>` dengan ID tadi):
```yaml
tunnel: <Tunnel-UUID>
credentials-file: /home/pi/.cloudflared/<Tunnel-UUID>.json

ingress:
  # Arahkan domain ke aplikasi lokal di port 5000
  - hostname: app.domainanda.com
    service: http://localhost:5000
    
  # Catch-all rule (wajib ada di akhir)
  - service: http_status:404
```

### 5. Routing DNS (Penting!)
Supaya `app.domainanda.com` nyambung ke tunnel ini:
```bash
cloudflared tunnel route dns mba-app app.domainanda.com
```

### 6. Jalankan Tunnel
Coba jalankan manual dulu:
```bash
cloudflared tunnel run mba-app
```
Sekarang buka `https://app.domainanda.com`. Harusnya aplikasi MBA Automation sudah muncul dengan Gembok Hijau! 🔒

---

## LANGKAH 2: Bikin Otomatis (Service)

Supaya kalau Raspi mati lampu & nyala lagi, tunnel otomatis jalan:

```bash
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared
```

---

## KELEBIHAN CARA INI:
1.  **GRATIS**: Cloudflare Tunnel 100% Free.
2.  **AMAN**: IP asli rumah agan tidak terekspos.
3.  **HTTPS**: Otomatis dapat SSL (aman dari sadap).
4.  **BYE VPS**: Agan sebenarnya **TIDAK BUTUH VPS** lagi kalau pakai cara ini (kecuali buat kebutuhan lain). Raspi di rumah sudah cukup!
