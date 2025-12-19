# Panduan Perbaikan Otomasi di Termux

Jika otomasi di Termux tidak jalan atau dashboard muncul "60/60" terus (stale), ikuti langkah-langkah berikut:

## 1. Perbaiki Crontab di Termux
Buka Termux dan jalankan perintah untuk mengedit crontab:
```bash
crontab -e
```

Ganti isinya dengan format yang benar (hapus kata `run` dan pastikan path sesuai):
```bash
# Ganti ~/projects/mba-automation dengan path folder agan jika beda
10 0 * * * cd ~/projects/mba-automation && python -m mba_automation.cli --phone 6282129002163 --headless >> ~/projects/mba-automation/logs/cron_82129002163.log 2>&1
14 0 * * * cd ~/projects/mba-automation && python -m mba_automation.cli --phone 6285117678844 --headless >> ~/projects/mba-automation/logs/cron_85117678844.log 2>&1
```

## 2. Pastikan Server Webapp Jalan
Jangan lupa jalankan server dashboard di Termux agar scheduler internalnya aktif:
```bash
cd ~/projects/mba-automation
python webapp.py
```

## 3. Cek Log Kesalahan
Jika masih tidak jalan, cek file log di Termux:
```bash
cat ~/projects/mba-automation/logs/cron_82129002163.log
```

> [!IMPORTANT]
> Di Termux, biasanya perintahnya cukup `python` (bukan `python3` atau `.venv/bin/python`) kecuali agan pakai virtual environment khusus di Termux.
