import json
import datetime
import os
import sys

ACCOUNTS_FILE = "accounts.json"

if not os.path.exists(ACCOUNTS_FILE):
    print("❌ Critical: accounts.json not found!")
    sys.exit(1)

try:
    with open(ACCOUNTS_FILE, 'r') as f:
        accounts = json.load(f)
except Exception as e:
    print(f"❌ Critical: Failed to load accounts.json: {e}")
    sys.exit(1)

print(f"📋 Loaded {len(accounts)} accounts.")
now = datetime.datetime.now()
print(f"🕒 System Time: {now}")
print(f"📅 Weekday: {now.weekday()} (0=Mon, 6=Sun)")

if now.weekday() == 6:
    print("⚠️  Warning: Today is SUNDAY. Scheduler does NOT run on Sundays.")

print("-" * 50)

for acc in accounts:
    phone = acc.get('phone', 'Unknown')
    schedule = acc.get('schedule')
    last_run = acc.get('last_run_ts')
    is_syncing = acc.get('is_syncing')
    
    print(f"👤 Account: {phone}")
    print(f"   Settings: Schedule='{schedule}', In-Sync={is_syncing}")
    print(f"   Last Run: {last_run}")
    
    if is_syncing:
        print("   ❌ STATUS: BLOCKED (is_syncing is True)")
        continue

    if not schedule:
        print("   ⚪ STATUS: SKIPPED (No schedule set)")
        continue

    try:
        hh, mm = (int(x) for x in schedule.split(':'))
        scheduled_dt = datetime.datetime.combine(now.date(), datetime.time(hh, mm))
        
        print(f"   Target:   {scheduled_dt}")
        
        if now < scheduled_dt:
             diff = scheduled_dt - now
             print(f"   ⏳ STATUS: WAITING (Will run in {diff})")
        else:
             # Check last run
             should_run = True
             if last_run:
                 try:
                     last_dt = datetime.datetime.fromisoformat(last_run)
                     # Tolerance 10s
                     if last_dt >= scheduled_dt - datetime.timedelta(seconds=10):
                          print(f"   ✅ STATUS: DONE (Ran at {last_dt})")
                          should_run = False
                 except ValueError:
                     print("   ⚠️  Warning: Invalid last_run format, treating as never ran.")
             
             if should_run:
                 print("   🚀 STATUS: DUE! (Should trigger soon)")
                 
    except ValueError:
        print(f"   ⚠️  ERROR: Invalid schedule format '{schedule}'")

print("-" * 50)
