import json
import os

ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "accounts.json")

def reset_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        print(f"File not found: {ACCOUNTS_FILE}")
        return

    try:
        with open(ACCOUNTS_FILE, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)

        count = 0
        for acc in data:
            # Reset status if it's 'running' or 'queued'
            if acc.get('status') in ['running', 'queued']:
                print(f"Resetting account {acc.get('phone')} (was {acc.get('status')})")
                acc['status'] = 'idle'
                acc['is_syncing'] = False
                count += 1
        
        if count > 0:
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"✅ Successfully reset {count} stuck accounts.")
        else:
            print("No stuck accounts found.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    reset_accounts()
