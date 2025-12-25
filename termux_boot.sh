#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
cd ~/projects/mba-automation
# Kill existing instance if any (unlikely on fresh boot but good practice)
pkill -f webapp.py
# Start webapp in background
nohup python webapp.py > boot.log 2>&1 &
