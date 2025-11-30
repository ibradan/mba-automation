import json
import subprocess
import sys
import os

# Load accounts
with open('accounts.json', 'r') as f:
    accounts = json.load(f)

print(f"Syncing progress for {len(accounts)} accounts...")

for acc in accounts:
    phone = acc['phone']
    # Remove 62 prefix for CLI if present, though CLI handles it
    phone_display = phone[2:] if phone.startswith('62') else phone
    password = acc['password']
    
    print(f"Syncing {phone}...")
    try:
        # Run CLI in headless mode
        subprocess.run(
            [sys.executable, "-m", "mba_automation.cli", "--phone", phone_display, "--password", password, "--headless"],
            check=True
        )
        print(f"✓ {phone} synced.")
    except Exception as e:
        print(f"✗ Failed to sync {phone}: {e}")

print("Batch sync complete.")
