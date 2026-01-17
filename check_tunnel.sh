#!/bin/bash
# check_tunnel.sh - Diagnostic script for SSH Tunnel

echo "🔍 Checking SSH Tunnel Status..."
echo "--------------------------------"

# 1. Cek Service Autossh
echo "1. Service Status:"
systemctl status autossh-tunnel --no-pager | grep "Active:"
echo ""

# 2. Cek Process Running
echo "2. Process Check:"
ps aux | grep "[a]utossh"
ps aux | grep "[s]sh -N"
echo ""

# 3. Cek Log Error Terakhir
echo "3. Last 10 Error Logs:"
journalctl -u autossh-tunnel -n 10 --no-pager | grep "Error"
echo ""

# 4. Tes Koneksi Lokal
echo "4. Local Web App Test (Raspi):"
curl -I localhost:5000 2>/dev/null | head -n 1 || echo "❌ Web App Down / Tidak merespon"
echo ""

echo "--------------------------------"
echo "✅ Diagnosa Selesai."
