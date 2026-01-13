#!/bin/bash
# Script to add 2GB swap file to prevent OOM
set -e

SWAP_FILE="/swapfile"
SWAP_SIZE="2G"

if [ -f "$SWAP_FILE" ]; then
    echo "Swap file already exists."
    ls -lh $SWAP_FILE
    exit 0
fi

echo "Creating $SWAP_SIZE swap file..."
sudo fallocate -l $SWAP_SIZE $SWAP_FILE
sudo chmod 600 $SWAP_FILE
sudo mkswap $SWAP_FILE
sudo swapon $SWAP_FILE

# Persist
if ! grep -q "$SWAP_FILE" /etc/fstab; then
    echo "$SWAP_FILE none swap sw 0 0" | sudo tee -a /etc/fstab
fi

echo "Swap created successfully!"
free -h
