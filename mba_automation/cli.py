import argparse
import os
# from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from .automation import run as automation_run


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
            completed, total = automation_run(playwright, phone=phone, password=password, headless=final_headless, slow_mo=args.slow_mo, iterations=args.iterations, review_text=args.review, viewport_name=args.viewport, timeout=args.timeout)
            
            # Save progress to accounts.json
            try:
                import json
                import datetime
                import fcntl
                
                accounts_file = os.path.join(os.path.dirname(__file__), '..', 'accounts.json')
                accounts_file = os.path.abspath(accounts_file)
                
                # Normalize phone (add 62 prefix if needed)
                normalized_phone = phone if phone.startswith('62') else '62' + phone
                
                # Calculate percentage
                percentage = round((completed / total) * 100) if total > 0 else 0
                
                # Read, update, write with file locking
                if os.path.exists(accounts_file):
                    with open(accounts_file, 'r+') as f:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                        try:
                            accounts = json.load(f)
                            # Find and update account
                            for acc in accounts:
                                if acc.get('phone') == normalized_phone:
                                    today = datetime.datetime.now().strftime('%Y-%m-%d')
                                    if 'daily_progress' not in acc:
                                        acc['daily_progress'] = {}
                                    acc['daily_progress'][today] = {
                                        'completed': completed,
                                        'total': total,
                                        'percentage': percentage
                                    }
                                    break
                            # Write back
                            f.seek(0)
                            f.truncate()
                            json.dump(accounts, f, indent=2)
                        finally:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                
                print(f"✓ Progress saved: {completed}/{total} ({percentage}%)")
            except Exception as e:
                print(f"Warning: Could not save progress: {e}")


if __name__ == "__main__":
    main()
