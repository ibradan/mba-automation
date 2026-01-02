import json
import datetime
import fcntl
import signal
import sys
import re
import os
import argparse
import time
import gc
from playwright.sync_api import sync_playwright
from .automation import run as automation_run

ACCOUNTS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'accounts.json'))

# Global state for signal handler
current_run_data = {
    'phone': None,
    'completed': 0,
    'total': 0,
    'income': 0.0,
    'withdrawal': 0.0,
    'balance': 0.0,
    'points': 0.0,
    'calendar': [],
    'is_sync': False
}

def normalize_phone(phone: str) -> str:
    """Standard normalization: ensure starts with 62."""
    if not phone: return ""
    p = re.sub(r'\D', '', str(phone))
    if p.startswith('0'): p = '62' + p[1:]
    elif p.startswith('8'): p = '62' + p
    return p

def save_progress() -> None:
    """Atomically save current progress to accounts.json."""
    data = current_run_data
    if not data['phone']:
        return

    try:
        with open(ACCOUNTS_FILE, 'r+') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                accounts = json.load(f)
                updated = False
                today = datetime.datetime.now().strftime('%Y-%m-%d')
                norm_target = normalize_phone(data['phone'])

                for acc in accounts:
                    if normalize_phone(acc.get('phone')) == norm_target:
                        if 'daily_progress' not in acc:
                            acc['daily_progress'] = {}
                        
                        existing = acc['daily_progress'].get(today, {})
                        
                        # Sticky Progress
                        final_completed = max(data['completed'], existing.get('completed', 0))
                        final_total = max(data['total'], existing.get('total', 0))
                        
                        # Sticky Financials
                        final_income = data['income'] if (data['income'] > 0 or not existing) else existing.get('income', 0.0)
                        final_withdrawal = data['withdrawal'] if (data['withdrawal'] > 0 or not existing) else existing.get('withdrawal', 0.0)
                        final_balance = data['balance'] if (data['balance'] > 0 or not existing) else existing.get('balance', 0.0)
                        final_points = data['points'] if (data['points'] > 0 or not existing) else existing.get('points', 0.0)
                        final_calendar = data['calendar'] if (len(data['calendar']) > 0 or not existing) else existing.get('calendar', [])

                        acc['daily_progress'][today] = {
                            'date': today,
                            'completed': final_completed,
                            'total': final_total,
                            'percentage': int((final_completed / final_total) * 100) if final_total > 0 else 0,
                            'income': final_income,
                            'withdrawal': final_withdrawal,
                            'balance': final_balance,
                            'points': final_points,
                            'calendar': final_calendar
                        }
                        
                        ts = datetime.datetime.now().isoformat()
                        acc['last_sync_ts'] = ts
                        if not data['is_sync']:
                            acc['last_run_ts'] = ts
                        
                        acc['is_syncing'] = False
                        updated = True
                        break
                
                if updated:
                    f.seek(0)
                    json.dump(accounts, f, indent=2)
                    f.truncate()
                    print(f"✓ Progress saved for {data['phone']}")
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception as e:
        print(f"⚠️ Failed to save progress: {e}")

def signal_handler(sig, frame):
    print(f"\nTerminating (signal {sig}). Saving progress...")
    save_progress()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def check_internet_connection() -> bool:
    """Simple check for internet connectivity."""
    try:
        # connect to a reliable DNS server (Google DNS)
        # We don't need to send data, just establish connection
        import socket
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        pass
    return False

def main() -> None:
    parser = argparse.ArgumentParser(description="MBA7 automation CLI")
    # allow multiple phones via repeated --phone or comma-separated --phones
    parser.add_argument("--phone", dest="phones", action="append", help="Phone number (can be provided multiple times; overrides .env)")
    parser.add_argument("--phones", dest="phones_csv", help="Comma-separated phone numbers (overrides .env)")
    parser.add_argument("--password", help="Password (overrides .env)")
    # allow explicit --headless / --no-headless and default to environment or True
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--headless", dest="headless", action="store_true", help="Run browser headless")
    group.add_argument("--no-headless", dest="headless", action="store_false", help="Run browser with visible UI (not headless)")
    parser.set_defaults(headless=None)
    parser.add_argument("--slow-mo", type=int, default=200, help="Playwright slowMo in ms")
    parser.add_argument("--iterations", type=int, default=30, help="Number of review loops")
    parser.add_argument("--review", type=str, default=None, help="Optional review text to submit")
    parser.add_argument("--sync", action="store_true", help="Sync financial data only (skips tasks loop)")
    args = parser.parse_args()

    # load .env if present
    # load_dotenv()

    # assemble phone list from CLI args and environment variables
    phones = []
    if args.phones:
        phones.extend([p for p in args.phones if p])
    if args.phones_csv:
        phones.extend([p.strip() for p in args.phones_csv.split(",") if p.strip()])

    # fall back to env vars: MBA_PHONE or MBA_PHONES (comma-separated)
    env_phone = os.getenv("MBA_PHONE")
    env_phones = os.getenv("MBA_PHONES")
    if env_phone:
        phones.append(env_phone)
    if env_phones:
        phones.extend([p.strip() for p in env_phones.split(",") if p.strip()])

    password = args.password or os.getenv("MBA_PASSWORD")

    if not phones or not password:
        print("ERROR: at least one phone and a password must be provided via args or .env (MBA_PHONE or MBA_PHONES, MBA_PASSWORD)")
        return

    # run automation sequentially for each phone
    with sync_playwright() as playwright:
        # SYSTEM CLEANUP: Delete logs older than 3 days
        LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
        if os.path.exists(LOGS_DIR):
            print("🧹 Cleaning up old logs...")
            now = time.time()
            for f in os.listdir(LOGS_DIR):
                f_path = os.path.join(LOGS_DIR, f)
                if os.path.isfile(f_path) and os.stat(f_path).st_mtime < now - 3 * 86400:
                    try: 
                        os.remove(f_path)
                        print(f"  Removed old log: {f}")
                    except: pass

        # Decide final headless setting: CLI flag > env var > default True
        env_headless = os.getenv("MBA_HEADLESS")
        def env_bool(v):
            if v is None:
                return None
            return str(v).strip().lower() in ("1","true","yes","on")

        if args.headless is not None:
            final_headless = bool(args.headless)
        else:
            parsed = env_bool(env_headless)
            final_headless = True if parsed is None else bool(parsed)

        for phone in phones:
            print(f"Starting automation for {phone} (headless={final_headless})")
            
            current_run_data.update({
                'phone': phone,
                'completed': 0,
                'total': args.iterations,
                'income': 0.0,
                'withdrawal': 0.0,
                'balance': 0.0,
                'points': 0.0,
                'calendar': [],
                'is_sync': args.sync
            })
            
            max_retries = 5
            attempt = 0
            while attempt < max_retries:
                attempt += 1
                if attempt > 1:
                    print(f"🔄 Retry attempt {attempt}/{max_retries} for {phone}...")
                    
                    # Connection Check
                    if not check_internet_connection():
                        print("⚠️ No internet connection detected. Waiting 30s...")
                        time.sleep(30)
                
                def on_prog(c, t):
                    current_run_data.update({
                        'completed': c,
                        'total': t
                    })
                    save_progress()

                try:
                    c, t, i, w, b, p, cal = automation_run(
                        playwright, phone=phone, password=password, 
                        headless=final_headless, slow_mo=args.slow_mo, 
                        iterations=args.iterations, review_text=args.review, 
                        sync_only=args.sync, progress_callback=on_prog
                    )
                    
                    # Update global data for persistence
                    current_run_data.update({
                        'completed': c,
                        'total': t,
                        'income': i,
                        'withdrawal': w,
                        'balance': b,
                        'points': p,
                        'calendar': cal
                    })
                    
                    if args.sync or (c >= t and t > 0):
                        print(f"✅ {'SYNC' if args.sync else 'SUCCESS'} for {phone}")
                        # COOL DOWN: Give the CPU a break before next account
                        if phone != phones[-1]:
                            print("❄️ Cooling down for 15s...")
                            time.sleep(15)
                        # Explicit Memory Flush
                        gc.collect()
                        break
                    
                    print(f"⚠️ Incomplete: {c}/{t}. Retrying in 5s...")
                    time.sleep(5)
                except Exception as e:
                    print(f"❌ Error: {e}. Retrying in 5s...")
                    time.sleep(5)
            
            save_progress()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
