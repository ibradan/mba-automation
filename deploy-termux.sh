#!/bin/bash
# deploy-termux.sh - Deploy from WSL to Termux (Android)

# --- KONFIGURASI ---
# Ganti dengan IP HP agan (cek di Termux pakai perintah 'ifconfig' atau 'ip addr')
TERMUX_IP="192.168.0.227" 
TERMUX_PORT="8022"
# Path di Termux (default $HOME/projects/mba-automation)
REMOTE_PATH="~/projects/mba-automation"

if [ "$TERMUX_IP" == "192.168.0.XXX" ]; then
    echo "❌ Error: Silakan buka file ini dan ganti TERMUX_IP dengan IP HP agan!"
    exit 1
fi

echo "🚀 Mempersiapkan pengiriman data ke Termux (${TERMUX_IP})..."

# 1. Pastikan folder tujuan ada
ssh -p ${TERMUX_PORT} ${TERMUX_IP} "mkdir -p ${REMOTE_PATH}"

echo "📦 Mengirim file project..."

# 2. Kirim file & folder (Tanpa .venv dan logs biar enteng)
scp -P ${TERMUX_PORT} -r \
    mba_automation \
    templates \
    static \
    webapp.py \
    requirements.txt \
    accounts.json \
    settings.json \
    docs \
    ${TERMUX_IP}:${REMOTE_PATH}/

echo "✅ Berhasil dikirim ke Termux!"
echo "----------------------------------------------------"
echo "Langkah selanjutnya di HP agan:"
echo "1. Buka Termux"
echo "2. Masuk ke folder: cd ${REMOTE_PATH}"
echo "3. Jalankan server: python webapp.py"
echo "----------------------------------------------------"
