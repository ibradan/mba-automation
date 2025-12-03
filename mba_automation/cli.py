import argparse
import os
import time
# from dotenv import load_dotenv
import json
import datetime
import fcntl
from playwright.sync_api import sync_playwright
from .automation import run as automation_run

ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), '..', 'accounts.json')
ACCOUNTS_FILE = os.path.abspath(ACCOUNTS_FILE)


def main():
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
    parser.add_argument("--viewport", type=str, default="iPhone 12", help="Device viewport name (e.g., 'iPhone 12')")
    parser.add_argument("--timeout", type=int, default=30, help="Navigation timeout in seconds")
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
            
            # Retry loop to ensure completion
            max_retries = 50
            attempt = 0
            completed = 0
            total = args.iterations
            income = 0.0
            withdrawal = 0.0
            balance = 0.0

            while attempt < max_retries:
                attempt += 1
                if attempt > 1:
                    print(f"🔄 Retry attempt {attempt}/{max_retries} for {phone}...")
                
                try:
                    completed, total, income, withdrawal, balance = automation_run(playwright, phone=phone, password=password, headless=final_headless, slow_mo=args.slow_mo, iterations=args.iterations, review_text=args.review, viewport_name=args.viewport, timeout=args.timeout)
                    
                    if completed >= total and total > 0:
                        print(f"✅ SUCCESS: {phone} completed all tasks ({completed}/{total})")
                        break
                    
                    print(f"⚠️ Incomplete: {completed}/{total}. Retrying in 5s...")
                    time.sleep(5)
                except Exception as e:
                    print(f"❌ Error during run: {e}. Retrying in 5s...")
                    time.sleep(5)
            
            if completed < total:
                print(f"❌ FAILED: Could not complete tasks for {phone} after {max_retries} attempts.")
            
            # Save progress to accounts.json
            try:
                with open(ACCOUNTS_FILE, 'r+') as f:
                    # Use file locking to prevent race conditions
                    fcntl.flock(f, fcntl.LOCK_EX)
                    try:
                        data = json.load(f)
                        updated = False
                        today = datetime.datetime.now().strftime('%Y-%m-%d')
                        
                        for acc in data:
                            # Normalize phone (add 62 prefix if needed) for comparison
                            normalized_phone_in_file = acc.get('phone')
                            if normalized_phone_in_file and not normalized_phone_in_file.startswith('62'):
                                normalized_phone_in_file = '62' + normalized_phone_in_file
                            
                            normalized_current_phone = phone if phone.startswith('62') else '62' + phone

                            if normalized_phone_in_file == normalized_current_phone:
                                if 'daily_progress' not in acc:
                                    acc['daily_progress'] = {}
                                
                                acc['daily_progress'][today] = {
                                    'completed': completed,
                                    'total': total,
                                    'percentage': int((completed / total) * 100) if total > 0 else 0,
                                    'income': income,
                                    'withdrawal': withdrawal,
                                    'balance': balance
                                }
                                acc['last_run_ts'] = datetime.datetime.now().isoformat()
                                updated = True
                                break
                        
                        if updated:
                            f.seek(0)
                            json.dump(data, f, indent=2)
                            f.truncate()
                            print(f"✓ Progress saved: {completed}/{total} ({int((completed/total)*100)}%) - Income: Rp {income:,.0f} - Withdrawal: Rp {withdrawal:,.0f} - Balance: Rp {balance:,.0f}")
                        else:
                            print(f"Warning: Account {phone} not found in accounts.json")
                            
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)
            except Exception as e:
                print(f"Warning: Could not save progress: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
