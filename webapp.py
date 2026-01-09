from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
import subprocess
import sys
import os
import shlex
import datetime
import json
import re
import threading
import time
import logging
from logging.handlers import RotatingFileHandler
import queue
import fcntl
try:
    import requests
except ImportError:
    requests = None
from utils import crypto


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "please-change-this")


# Auth Helpers
def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_users(users):
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
        return True
    except:
        return False

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = load_users()
        user = next((u for u in users if u['username'] == username), None)
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['username']
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not username or not password:
            flash('Username dan password wajib diisi', 'error')
            return redirect(url_for('register'))
            
        if password != confirm_password:
            flash('Password tidak cocok', 'error')
            return redirect(url_for('register'))
            
        users = load_users()
        if any(u['username'] == username for u in users):
            flash('Username sudah digunakan', 'error')
            return redirect(url_for('register'))
            
        new_user = {
            'username': username,
            'password_hash': generate_password_hash(password)
        }
        users.append(new_user)
        
        if save_users(users):
            flash('Registrasi berhasil! Silakan login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Gagal menyimpan user baru', 'error')
            
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not old_password or not new_password:
        flash('Password lama dan baru wajib diisi.', 'error')
        return redirect(url_for('index'))
    
    if new_password != confirm_password:
        flash('Password baru tidak cocok.', 'error')
        return redirect(url_for('index'))
        
    current_username = session.get('user_id')
    users = load_users()
    user = next((u for u in users if u['username'] == current_username), None)
    
    if not user:
        flash('User tidak ditemukan.', 'error')
        return redirect(url_for('index'))
        
    if not check_password_hash(user['password_hash'], old_password):
        flash('Password lama salah.', 'error')
        return redirect(url_for('index'))
        
    # Update password
    user['password_hash'] = generate_password_hash(new_password)
    
    if save_users(users):
        flash('Password berhasil diubah!', 'success')
    else:
        flash('Gagal menyimpan password baru.', 'error')
        
    return redirect(url_for('index'))

# PWA Routes (must be at root for proper scope)
@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')


LOG_FILE = os.path.join(os.path.dirname(__file__), "runs.log")
ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "accounts.json")
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
SCHED_LOCK = threading.Lock()
USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")

# LRU Cache for accounts data (SAFE OPTIMIZATION)
class LRUCache:
    def __init__(self, max_size=10, ttl=30):
        self.cache = {}
        self.timestamps = {}
        self.max_size = max_size
        self.ttl = ttl
        self.lock = threading.Lock()
    
    def get(self, key):
        with self.lock:
            if key in self.cache:
                if time.time() - self.timestamps[key] < self.ttl:
                    return self.cache[key]
                else:
                    del self.cache[key]
                    del self.timestamps[key]
            return None
    
    def set(self, key, value):
        with self.lock:
            if len(self.cache) >= self.max_size:
                oldest = min(self.timestamps, key=self.timestamps.get)
                del self.cache[oldest]
                del self.timestamps[oldest]
            self.cache[key] = value
            self.timestamps[key] = time.time()
    
    def invalidate(self):
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()

ACCOUNTS_CACHE = LRUCache(max_size=10, ttl=30)

# Priority Job Queue (SAFE OPTIMIZATION)
JOB_QUEUE = queue.PriorityQueue()
JOB_TRACKING = {}  # Track running jobs
JOB_TRACKING_LOCK = threading.Lock()
ACTIVE_JOBS = 0
ACTIVE_JOBS_LOCK = threading.Lock()

def worker():
    """Background worker to process automation jobs serially."""
    while True:
        job = None
        try:
            job = JOB_QUEUE.get()
            if job is None:
                break
            
            cmd = job.get('cmd')
            log_file = job.get('log_file')
            phone_display = job.get('phone_display')
            is_sync = job.get('is_sync', False)
            
            logger.info(f"QUEUE: Starting job for {phone_display} (Sync={is_sync})")
            
            with ACTIVE_JOBS_LOCK:
                global ACTIVE_JOBS
                ACTIVE_JOBS += 1
            
            try:
                # Open file for writing
                with open(log_file, "w") as f:
                    # Run synchronously - creating a BLOCKING call here
                    subprocess.run(cmd, cwd=os.path.dirname(__file__), stdout=f, stderr=subprocess.STDOUT)
                
                # Send Telegram Notification (Skip if it's just a sync job)
                if not is_sync:
                    def _send_tele_safe():
                        try:
                            # Reload accounts to get the latest progress update from the CLI run
                            # We create a new DataManager instance here to avoid lock contention if needed,
                            # but utilizing the thread-safe read from main instance is also okay.
                            # For simplicity, let's just use the logic directly.
                            
                            # Note: data_manager methods use a lock.
                            accounts_data = data_manager.load_accounts()
                            norm_p = normalize_phone(phone_display)
                            acc_info = next((a for a in accounts_data if normalize_phone(a.get('phone', '')) == norm_p), None)
                            
                            if acc_info:
                                today_str = datetime.datetime.now().strftime('%Y-%m-%d')
                                prog = acc_info.get('daily_progress', {}).get(today_str, {})
                                
                                # Format as currency-like string
                                def fmt_rp(val):
                                    try: return f"{int(float(val or 0)):,}".replace(',', '.')
                                    except: return str(val or 0)

                                header = "✅ <b>Tugas Selesai!</b>"
                                msg = (
                                    f"{header} ({phone_display})\n\n"
                                    f"📊 Progress: <b>{prog.get('completed', 0)}/{prog.get('total', 60)}</b> ({prog.get('percentage', 0)}%)\n"
                                    f"💵 Saldo: <code>Rp {fmt_rp(prog.get('balance'))}</code>\n\n"
                                    f"<i>Automasi sukses dijalankan! 🔥</i>"
                                )
                                data_manager.send_telegram_msg(msg)
                            else:
                                data_manager.send_telegram_msg(f"✅ <b>Tugas Selesai!</b>\nAkun: <code>{phone_display}</code>\nStatus: Berhasil.")
                        except Exception as tele_e:
                            logger.error(f"Failed to send detailed Telegram: {tele_e}")
                    
                    # Fire and forget thread
                    threading.Thread(target=_send_tele_safe, daemon=True).start()
                
                logger.info(f"QUEUE: Finished job for {phone_display}")
            except Exception as e:
                logger.exception(f"QUEUE: Job failed for {phone_display}: {e}")
            finally:
                with ACTIVE_JOBS_LOCK:
                    ACTIVE_JOBS -= 1
                
        except Exception as e:
            logger.exception(f"Worker exception: {e}")
        finally:
            if job is not None:
                JOB_QUEUE.task_done()

# NOTE: Worker threads will be started after logger and data_manager are initialized

def clean_old_logs():
    """Delete log files older than 3 days in the logs directory."""
    while True:
        try:
            log_dir = os.path.join(os.path.dirname(__file__), "logs")
            if os.path.exists(log_dir):
                now = time.time()
                retention_seconds = 3 * 24 * 3600 # 3 days
                for f in os.listdir(log_dir):
                    f_path = os.path.join(log_dir, f)
                    if os.path.isfile(f_path):
                        if os.stat(f_path).st_mtime < now - retention_seconds:
                            try:
                                os.remove(f_path)
                                logger.info(f"CLEANUP: Removed old log file {f}")
                            except: pass
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        time.sleep(3600) # Check every hour

# Start cleanup thread
cleanup_thread = threading.Thread(target=clean_old_logs, daemon=True)
cleanup_thread.start()



class DataManager:
    """Encapsulates all interactions with accounts.json and settings.json."""
    
    def __init__(self):
        self.accounts_file = ACCOUNTS_FILE
        self.settings_file = SETTINGS_FILE
        self.lock = threading.Lock()

    def load_settings(self):
        """Load settings from JSON file with error handling."""
        if not os.path.exists(self.settings_file):
            return {}
        try:
            with open(self.settings_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            return {}

    def save_settings(self, settings):
        """Save settings to JSON file with error handling."""
        try:
            temp_file = self.settings_file + '.tmp'
            with open(temp_file, 'w') as f:
                json.dump(settings, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, self.settings_file)
            return True
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def load_accounts(self):
        """Load accounts with shared lock to prevent reading during a write."""
        with self.lock:
            if not os.path.exists(self.accounts_file):
                return []
            try:
                with open(self.accounts_file, 'r') as f:
                    try:
                        fcntl.flock(f, fcntl.LOCK_SH)
                        data = json.load(f)
                        # Decrypt passwords on load
                        for acc in data:
                            if 'password' in acc:
                                acc['password'] = crypto.decrypt_password(acc['password'])
                        return data
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)
            except Exception as e:
                logger.warning("WARNING failed to read accounts file: %s", e)
                return []

    def atomic_update_accounts(self, update_fn):
        """Atomically update accounts.json using a file lock."""
        with self.lock:
            # Create file if not exists
            if not os.path.exists(self.accounts_file):
                try:
                    with open(self.accounts_file, 'w') as f:
                        json.dump([], f)
                except Exception:
                    pass

            # Backup logic
            self._backup_accounts()

            try:
                with open(self.accounts_file, 'r+') as f:
                    fcntl.flock(f, fcntl.LOCK_EX)
                    try:
                        try:
                            f.seek(0)
                            accounts = json.load(f)
                        except json.JSONDecodeError:
                            accounts = []
                        
                        # Decrypt BEFORE passing to update function
                        for acc in accounts:
                            if 'password' in acc:
                                acc['password'] = crypto.decrypt_password(acc['password'])
                        
                        new_accounts = update_fn(accounts)
                        
                        # Encrypt BEFORE saving
                        for acc in new_accounts:
                            if 'password' in acc:
                                acc['password'] = crypto.encrypt_password(acc['password'])
                        
                        f.seek(0)
                        f.truncate()
                        json.dump(new_accounts, f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                        return True
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)
            except Exception as e:
                logger.error("Failed atomic update: %s", e)
                return False

    def _backup_accounts(self):
        """Internal helper for rotating backups of accounts.json."""
        try:
            backup_dir = os.path.join(os.path.dirname(self.accounts_file), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            max_backups = 5
            base_name = os.path.join(backup_dir, 'accounts.json.bak')
            
            if os.path.exists(f"{base_name}.{max_backups}"):
                 try: os.remove(f"{base_name}.{max_backups}")
                 except: pass
            
            for i in range(max_backups - 1, 0, -1):
                src = f"{base_name}.{i}"
                dst = f"{base_name}.{i+1}"
                if os.path.exists(src):
                    try: os.rename(src, dst)
                    except: pass
            
            if os.path.exists(self.accounts_file):
                import shutil
                try: 
                    shutil.copy2(self.accounts_file, f"{base_name}.1")
                except: pass
        except Exception as e:
            logger.warning("Backup failed: %s", e)

    def write_accounts(self, accounts):
        """Legacy wrapper for simple overwrite."""
        return self.atomic_update_accounts(lambda _: accounts)

    def send_telegram_msg(self, message):
        """Send a message via Telegram Bot API using settings."""
        if requests is None:
            logger.warning("Telegram NOT SENT: requests module not installed.")
            return False

        settings = self.load_settings()
        token = settings.get('telegram_token')
        chat_id = settings.get('telegram_chat_id')
        
        if not token or not chat_id:
            logger.warning("Telegram NOT SENT: Missing token or chat_id in settings")
            return False
            
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("Telegram message sent successfully")
                return True
            else:
                logger.error(f"Telegram failed: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram exception: {e}")
            return False

data_manager = DataManager()


def _format_phone_for_cli(raw_phone: str) -> str:
    """Return phone string in display format expected by the CLI (no leading '62').
    Returns empty string if phone cannot be normalized.
    """
    if not raw_phone:
        return ''
    norm = normalize_phone(raw_phone)
    if not norm:
        return ''
    return norm[2:] if norm.startswith('62') else norm


# configure module-level logger writing to LOG_FILE (best-effort)
logger = logging.getLogger("mba-automation")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    try:
        handler = RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    except Exception:
        # fallback to basic logging to stderr when file not writable
        logging.basicConfig(level=logging.INFO)

# CRITICAL: Clear JOB_TRACKING on startup to prevent stale entries
with JOB_TRACKING_LOCK:
    JOB_TRACKING.clear()
logger.info("SYSTEM: Cleared job tracking (fresh start)")

# Load concurrency settings (SAFE: 5 workers, 30s cache, 15s scheduler)
_settings = data_manager.load_settings()
# Priority: Env Var > Settings File > Default (5)
env_workers = os.getenv('MBA_WORKERS')
default_workers = int(env_workers) if env_workers and env_workers.isdigit() else 5
MAX_WORKERS = int(_settings.get('max_workers', default_workers))
CACHE_TTL = int(_settings.get('cache_ttl', 30))
SCHED_CHECK_INTERVAL = int(_settings.get('scheduler_interval', 15))
ACCOUNTS_CACHE.ttl = CACHE_TTL

logger.info(f"SYSTEM: Starting {MAX_WORKERS} worker threads with {CACHE_TTL}s cache TTL")
logger.info(f"SCHEDULER: Check interval set to {SCHED_CHECK_INTERVAL}s")
for i in range(MAX_WORKERS):
    t = threading.Thread(target=worker, name=f"Worker-{i+1}", daemon=True)
    t.start()


def normalize_phone(raw: str) -> str:
    """Normalize various phone formats into a CLI-friendly digits-only string.
    Examples:
      "0812..." -> "62812..."
      "812..."  -> "62812..."
      "+62812"  -> "62812..."
      "62812"   -> "62812..."
    """
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if digits.startswith('0'):
        return '62' + digits[1:]
    if digits.startswith('8'):
        return '62' + digits
    if digits.startswith('62'):
        return digits
    return digits


def phone_display(normalized: str) -> str:
    """Convert stored normalized phone into the UI input value (without the +62 prefix).
    If normalized starts with '62', return the rest; otherwise return normalized.
    """
    if not normalized:
        return ''
    if normalized.startswith('62'):
        return normalized[2:]
    return normalized


@app.route("/api/accounts")
@login_required
def api_accounts():
    """Endpoint for real-time dashboard updates."""
    raw = data_manager.load_accounts()
    now = datetime.datetime.now()
    results = []
    
    
    current_user = session.get('user_id')
    for it in raw:
        # Filter by owner (default to admin if owner not set)
        owner = it.get('owner', 'admin')
        if owner != current_user:
            continue
            
        phone = it.get("phone", "")
        display = phone_display(phone)
        schedule = it.get('schedule', '')
        last_run_ts = it.get('last_run_ts')
        
        status = ''
        today_str = now.strftime('%Y-%m-%d')
        progress = it.get('daily_progress', {}).get(today_str, {})
        pct = progress.get('percentage', 0)
        
        if pct >= 99:
            status = 'ran'
            today_label = 'Today'
        elif pct > 0:
            status = 'due'
            today_label = 'Today'
        else:
            dp = it.get('daily_progress', {})
            today_label = 'Today'
            if dp:
                sorted_dates = sorted(dp.keys(), reverse=True)
                for d_str in sorted_dates:
                    try:
                        d_dt = datetime.datetime.fromisoformat(d_str)
                        if (now - d_dt).total_seconds() < 129600:
                            prev_progress = dp[d_str]
                            if prev_progress.get('percentage', 0) > 0:
                                progress = prev_progress
                                pct = progress.get('percentage', 0)
                                if pct >= 99: status = 'ran'
                                else: status = 'due'
                                today_label = f"Last ({d_str[-5:]})"
                                break
                    except: continue
            
            if status == '' and schedule:
                try:
                    hh, mm = (int(x) for x in schedule.split(':'))
                    scheduled_dt = datetime.datetime.combine(now.date(), datetime.time(hour=hh, minute=mm))
                    if scheduled_dt <= now:
                        status = 'due'
                    else:
                        status = 'pending'
                except: pass

        display_stats = progress if progress else {}
        if not display_stats or (display_stats.get('balance', 0) == 0 and display_stats.get('income', 0) == 0):
             dp = it.get('daily_progress', {})
             if dp:
                 sorted_dates = sorted(dp.keys(), reverse=True)
                 for d in sorted_dates:
                     if dp[d].get('balance', 0) > 0 or dp[d].get('income', 0) > 0:
                         display_stats = dp[d]
                         break
                 if not display_stats or (display_stats.get('balance', 0) == 0 and display_stats.get('income', 0) == 0):
                     display_stats = dp[sorted_dates[0]]

        raw_st = it.get('status', 'idle')
        label_map = {
            'running': 'Running ⚡',
            'queued': 'Queued ⏳',
            'failed': 'Failed ❌',
            'idle': 'Idle 💤'
        }
        
        results.append({
            "phone": phone,
            "phone_display": display,
            "status": status,
            "status_raw": raw_st,
            "status_label": label_map.get(raw_st, 'Idle'),
            "pct": pct,
            "completed": progress.get('completed', 0),
            "total": progress.get('total', 60),
            "income": display_stats.get('income', 0),
            "withdrawal": display_stats.get('withdrawal', 0) * 0.9, # Apply 10% tax
            "balance": display_stats.get('balance', 0),
            "points": display_stats.get('points', 0),
            "calendar": display_stats.get('calendar', []),
            "is_syncing": (
                it.get('is_syncing', False) and 
                it.get('sync_start_ts') and 
                (now - datetime.datetime.fromisoformat(it['sync_start_ts'])).total_seconds() < 300
            ) if it.get('sync_start_ts') else False,
            "today_label": today_label,
            "estimation": calculate_estimation(
                display_stats.get('income', 0), 
                display_stats.get('balance', 0),
                it.get('level') # Pass fallback level
            )
        })
    
    return jsonify({
        "accounts": results,
        "queue_size": JOB_QUEUE.qsize() + ACTIVE_JOBS
    })


def calculate_estimation(daily_income, current_balance, level_fallback=None):
    """
    Calculates financial estimation based on FIXED tier rates.
    E3: 150,000/day
    E2: 43,500/day
    E1: 15,000/day
    """
    try:
        balance = float(current_balance or 0)
    except:
        return None

    # Use the fallback level as the primary source for Tier
    tier = str(level_fallback or "Unknown").upper()
    
    # Force fixed income rates based on Tier as requested by user
    if tier == 'E3':
        income = 150000
        target_day_idx = 2 # Wednesday
        target_day_name = 'Rabu'
    elif tier == 'E2':
        income = 43500
        target_day_idx = 3 # Thursday
        target_day_name = 'Kamis'
    elif tier == 'E1':
        income = 15000
        target_day_idx = 4 # Friday
        target_day_name = 'Jumat'
    else:
        # Default or Basic
        income = 0
        target_day_idx = 4
        target_day_name = 'Jumat'
        if not level_fallback: return None

    # 2. Calculate Days Until Target
    now = datetime.datetime.now()
    current_weekday = now.weekday() # Mon=0, Sun=6
    
    # If today is target or after target, target is next week
    if current_weekday >= target_day_idx:
        days_until = (7 - current_weekday) + target_day_idx
    else:
        days_until = target_day_idx - current_weekday
        
    # 3. Calculate Projected Balance (SKIP SUNDAYS)
    projected_income = 0
    # Iterate through upcoming days
    for i in range(1, days_until + 1):
        future_date = now + datetime.timedelta(days=i)
        if future_date.weekday() != 6: # Skip Sunday
            projected_income += income
            
    estimated_total = balance + projected_income
    
    return {
        'tier': tier,
        'target_day': target_day_name,
        'days_left': days_until,
        'estimated_balance': estimated_total,
        'daily_income': income
    }


@app.route("/api/global_history")
@login_required
def api_global_history():
    """Aggregate historical data from all accounts for global chart with Forward Fill."""
    try:
        accounts = data_manager.load_accounts()
        aggregated = {}
        
        # 1. Collect all unique dates from all accounts
        all_dates = set()
        # 1. Collect all unique dates from all accounts
        all_dates = set()
        current_user = session.get('user_id')
        
        filtered_accounts = [
            a for a in accounts 
            if a.get('owner', 'admin') == current_user
        ]
        
        for acc in filtered_accounts:
            all_dates.update(acc.get('daily_progress', {}).keys())
            
        if not all_dates:
            return jsonify({})
            
        sorted_dates = sorted(list(all_dates))
        
        # 2. Iterative Forward Fill
        # We track the last known state for EACH account
        account_states = {} # {phone_norm: {'income': 0, ...}}

        for date_str in sorted_dates:
            # Stats for this specific date (aggregated across all accounts)
            day_total_income = 0
            day_total_balance = 0
            day_total_withdrawal = 0
            
            
            for acc in filtered_accounts:
                phone = normalize_phone(acc.get('phone', ''))
                if not phone: continue

                # Check if this account has specific data for this date
                daily_data = acc.get('daily_progress', {}).get(date_str)
                
                if daily_data:
                    # Update our knowledge of this account's state
                    account_states[phone] = {
                        'income': daily_data.get('income', 0),
                        'balance': daily_data.get('balance', 0),
                        'withdrawal': daily_data.get('withdrawal', 0)
                    }
                
                # Get the state to use (either just updated, or carried forward)
                current_state = account_states.get(phone, {
                    'income': 0, 'balance': 0, 'withdrawal': 0
                })
                
                day_total_income += current_state['income']
                day_total_balance += current_state['balance']
                day_total_withdrawal += (current_state['withdrawal'] * 0.9) # Apply 10% tax
            
            # Record the aggregates
            aggregated[date_str] = {
                'date': date_str,
                'income': day_total_income,
                'balance': day_total_balance,
                'withdrawal': day_total_withdrawal
            }
        
        return jsonify(aggregated)
    except Exception as e:
        logger.error(f"Global history error: {e}")
        return jsonify({}), 500


@app.route("/api/logs/<phone_display>")
@login_required
def api_phone_logs(phone_display):
    """Get the latest log content for a specific phone number."""
    try:
        # normalize to get the CLI format used in filenames
        norm = normalize_phone(phone_display)
        if not norm:
            return "Invalid phone number", 400
        
        # Logic matches _format_phone_for_cli
        phone_cli = norm[2:] if norm.startswith('62') else norm
        
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        if not os.path.exists(log_dir):
            return "No logs available yet.", 404
            
        # Find files matching pattern
        prefix = f"automation_{phone_cli}_"
        candidates = []
        for f in os.listdir(log_dir):
            if f.startswith(prefix) and f.endswith(".log"):
                candidates.append(os.path.join(log_dir, f))
        
        if not candidates:
            return "Log file not found for this account.", 404
            
        # Get the most recently modified file
        latest_log = max(candidates, key=os.path.getmtime)
        
        # Read content
        with open(latest_log, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            
        return content, 200, {'Content-Type': 'text/plain'}
        
    except Exception as e:
        logger.error(f"Log API Error: {e}")
        return str(e), 500


@app.route("/settings/get", methods=["GET"])
@login_required
def get_settings():
    return jsonify(data_manager.load_settings())


@app.route("/settings/save", methods=["POST"])
@login_required
def save_settings():
    try:
        data = request.get_json()
        if data_manager.save_settings(data):
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "Failed to save settings"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/settings/test_telegram", methods=["POST"])
@login_required
def test_telegram():
    """Endpoint to test Telegram configuration."""
    try:
        data = request.get_json()
        token = data.get('telegram_token')
        chat_id = data.get('telegram_chat_id')
        
        if not token or not chat_id:
             return jsonify({"status": "error", "message": "Bot Token dan Chat ID wajib diisi!"})
            
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": "<b>Koneksi Berhasil!</b>\n\nNotifikasi Ternak Uang sudah terhubung ke Telegram agan. 🔥",
            "parse_mode": "HTML"
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return jsonify({"status": "success", "message": "Pesan tes terkirim ke Telegram!"})
        else:
            return jsonify({"status": "error", "message": f"Gagal: {resp.text}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/export_accounts", methods=["GET"])
@login_required
def export_accounts():
    try:
        current_user = session.get('user_id')
        accounts = data_manager.load_accounts()
        # Filter for current user
        user_accounts = [acc for acc in accounts if acc.get('owner', 'admin') == current_user]
        
        return jsonify(user_accounts), 200, {
            'Content-Disposition': 'attachment; filename=accounts.json'
        }
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/import_accounts", methods=["POST"])
@login_required
def import_accounts():
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file part"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"status": "error", "message": "No selected file"}), 400
        if file:
            # Validate JSON
            try:
                data = json.load(file)
                if not isinstance(data, list):
                    return jsonify({"status": "error", "message": "Invalid format: expected a list of accounts"}), 400
                
                # Assign to current user
                current_user = session.get('user_id')
                for acc in data:
                    acc['owner'] = current_user
                    
                data_manager.write_accounts(data)
                return jsonify({"status": "success", "message": f"Imported {len(data)} accounts"})
            except json.JSONDecodeError:
                return jsonify({"status": "error", "message": "Invalid JSON file"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        phones = request.form.getlist('phone[]')
        passwords = request.form.getlist('password[]')
        levels = request.form.getlist('level[]')
        action = request.form.get('action')
        # form headless is submitted by JS as 'true' or 'false' (string). Fall back to env/default.
        val = request.form.get('headless')
        def parse_bool(v):
            if v is None:
                return None
            return str(v).strip().lower() in ("1","true","yes","on")

        form_headless = parse_bool(val)
        if form_headless is None:
            # No form value provided (older browsers/clients) -> respect env var or default True
            env_val = os.getenv('MBA_HEADLESS')
            env_b = parse_bool(env_val)
            headless = True if env_b is None else env_b
        else:
            headless = bool(form_headless)

        # normalize lists to same length
        entries = []
        for i, phone in enumerate(phones):
            phone = (phone or '').strip()
            if not phone:
                continue
            pwd = passwords[i].strip() if i < len(passwords) else ''
            lvl = levels[i].strip() if i < len(levels) else ''
            entries.append((phone, pwd, lvl))

        if not entries:
            flash("Isi minimal satu nomor HP.", "error")
            return redirect(url_for("index"))

        # If user only wants to save accounts, do that and return
        if action == 'save':
            try:
                def update_save(current_accounts):
                    current_user = session.get('user_id')
                    
                    # 1. Identify accounts to preserve (those NOT owned by current user)
                    preserved_accounts = [a for a in current_accounts if a.get('owner', 'admin') != current_user]
                    
                    # 2. Map MY existing accounts to preserve dynamic data
                    my_existing = {}
                    for a in current_accounts:
                        if a.get('owner', 'admin') == current_user:
                             norm_p = normalize_phone(a.get('phone'))
                             if norm_p: my_existing[norm_p] = a

                    new_list = []
                    for phone, pwd, lvl in entries:
                        norm = normalize_phone(phone)
                        # Start with fresh object
                        acc = {"phone": norm, "password": pwd, "level": (lvl or "E2"), "owner": current_user}
                        
                        # Preserve dynamic data from EXISTING file content
                        if norm in my_existing:
                            old = my_existing[norm]
                            # Copy persistent fields
                            for k in ['reviews', 'schedule', 'last_run', 'last_run_ts', 'last_sync_ts', 'daily_progress', 'is_syncing', 'sync_start_ts']:
                                if k in old: acc[k] = old[k]
                            
                        new_list.append(acc)
                    
                    # 3. Combine and return
                    return preserved_accounts + new_list

                if data_manager.atomic_update_accounts(update_save):
                     flash(f"{len(entries)} akun disimpan.", "success")
                else:
                     flash("Gagal menyimpan akun (file locked/error).", "error")

            except Exception as e:
                flash(f"Gagal menyimpan akun: {e}", "error")
            return redirect(url_for("index"))

        # Only run automation if explicitly requested
        if action == 'start':
            # load saved accounts to read per-account reviews (if any)
            saved_accounts = data_manager.load_accounts()

            started = 0
            for phone, pwd, lvl in entries:
                if not pwd:
                    flash(f"Password kosong untuk {phone}, dilewati.", "error")
                    continue

                # Map level strings to iterations: E1=15, E2=30, E3=60. If a numeric value was submitted, accept it.
                iterations = 30
                lvl_up = (lvl or '').upper()
                if lvl_up == 'E1':
                    iterations = 15
                elif lvl_up == 'E2':
                    iterations = 30
                elif lvl_up == 'E3':
                    iterations = 60
                else:
                    # fallback: allow numeric strings
                    try:
                        iterations = int(lvl)
                    except Exception:
                        iterations = 30

                # determine today's review text (if saved)
                review_text = None
                try:
                    norm_phone = normalize_phone(phone)
                    for a in saved_accounts:
                        if a.get('phone') == norm_phone:
                            r = a.get('reviews', {}) or {}
                            # weekday mapping: Monday=0 -> mon; note: no Sunday
                            wk = ['mon','tue','wed','thu','fri','sat']
                            wd = datetime.datetime.now().weekday()
                            # if today is Sunday (weekday 6) there's no review scheduled
                            if wd < len(wk):
                                key = wk[wd]
                                review_text = r.get(key) or None
                            else:
                                review_text = None
                            break
                except Exception:
                    review_text = None

                # use a consistent CLI phone format (display without leading 62)
                phone_for_cli = _format_phone_for_cli(phone)
                if not phone_for_cli:
                    flash(f"Nomor HP tidak valid: {phone}, dilewati.", "error")
                    continue

                cmd = [sys.executable, "-m", "mba_automation.cli", "--phone", phone_for_cli, "--password", pwd, "--iterations", str(iterations)]
                if review_text:
                    cmd.extend(["--review", review_text])
                if headless:
                    cmd.append("--headless")

                logger.info("ENQUEUE for %s: %s", phone, ' '.join(shlex.quote(c) for c in cmd))

                try:
                    # Create logs directory if it doesn't exist
                    log_dir = os.path.join(os.path.dirname(__file__), "logs")
                    os.makedirs(log_dir, exist_ok=True)
                    
                    # Generate log filename with timestamp
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    log_file = os.path.join(log_dir, f"automation_{phone_for_cli}_{timestamp}.log")
                    
                    # Add to Queue instead of Popen
                    JOB_QUEUE.put({
                        'cmd': cmd,
                        'log_file': log_file,
                        'phone_display': phone,
                        'is_sync': False
                    })
                    
                    started += 1
                    logger.info("Queued job logging to %s", log_file)
                except Exception as e:
                    # don't crash the request; log and show flash
                    logger.exception("FAILED ENQUEUE for %s: %s", phone_for_cli, e)
                    flash(f"Gagal memasukkan antrian untuk {phone}: {e}", "error")


            if started:
                flash(f"Automation started in background for {started} phone(s).", "success")

            # Persist submitted accounts so they can be reused later (update saved list)
            # Persist submitted accounts so they can be reused later (update saved list)
            try:
                def update_start(current_accounts):
                    current_user = session.get('user_id')
                    
                    # 1. Separate
                    other_accounts = [a for a in current_accounts if a.get('owner', 'admin') != current_user]
                    my_existing = [a for a in current_accounts if a.get('owner', 'admin') == current_user]
                    
                    existing_map = {}
                    for a in my_existing:
                        n = normalize_phone(a.get('phone'))
                        if n: existing_map[n] = a
                    
                    # 2. Rebuild Mine
                    my_new_list = []
                    for phone_in, pwd, lvl in entries:
                         norm = normalize_phone(phone_in)
                         acc = {"phone": norm, "password": pwd, "level": (lvl or "E2"), "owner": current_user}
                         if norm in existing_map:
                             old = existing_map[norm]
                             # Merge all persistent fields
                             for k in ['reviews', 'schedule', 'last_run', 'last_run_ts', 'last_sync_ts', 'daily_progress', 'is_syncing', 'sync_start_ts']:
                                 if k in old: acc[k] = old[k]
                         my_new_list.append(acc)
                    
                    # 3. Combine
                    return other_accounts + my_new_list

                data_manager.atomic_update_accounts(update_start)
            except Exception as e:
                # don't fail the request if saving fails
                logger.warning("WARNING saving accounts failed: %s", e)

        return redirect(url_for("index"))

    # GET: load saved accounts to prefill the form
    saved_accounts = []
    current_user = session.get('user_id')
    raw_all = data_manager.load_accounts()
    
    # Filter for display
    raw = [a for a in raw_all if a.get('owner', 'admin') == current_user]
    try:
        # prepare display form (strip leading country code for the visible input)
        now = datetime.datetime.now()
        for it in raw:
                    phone = it.get("phone", "")
                    pwd = it.get("password", "")
                    lvl = it.get("level", "E2")
                    display = phone_display(phone)
                    schedule = it.get('schedule', '')
                    # determine last run datetime (prefer ISO ts)
                    last_run_ts = it.get('last_run_ts')
                    last_run_dt = None
                    if last_run_ts:
                        try:
                            last_run_dt = datetime.datetime.fromisoformat(last_run_ts)
                        except Exception:
                            last_run_dt = None
                    else:
                        legacy = it.get('last_run')
                        if legacy:
                            try:
                                d = datetime.date.fromisoformat(legacy)
                                last_run_dt = datetime.datetime.combine(d, datetime.time(hour=0, minute=0))
                            except Exception:
                                last_run_dt = None

                    # compute status: 'ran' if already run at/after scheduled time today; 'due' if scheduled time passed but not run; 'pending' if scheduled in future or no schedule => ''
                    # compute status: 'ran' if 100% complete; 'due' if partial or scheduled time passed; 'pending' otherwise
                    status = ''
                    
                    # Check daily progress first
                    today_str = now.strftime('%Y-%m-%d')
                    progress = it.get('daily_progress', {}).get(today_str, {})
                    pct = progress.get('percentage', 0)
                    
                    if pct >= 99:
                        status = 'ran'
                        today_label = 'Today'
                    elif pct > 0:
                        status = 'due'
                        today_label = 'Today'
                    else:
                        # Extreme Resilience: Check the last 36 hours (handles massive time drift)
                        dp = it.get('daily_progress', {})
                        today_label = 'Today'
                        if dp:
                            sorted_dates = sorted(dp.keys(), reverse=True)
                            for d_str in sorted_dates:
                                try:
                                    d_dt = datetime.datetime.fromisoformat(d_str)
                                    # If this data is within 36 hours, use it as fallback
                                    if (now - d_dt).total_seconds() < 129600: # 36 hours
                                        prev_progress = dp[d_str]
                                        if prev_progress.get('percentage', 0) > 0:
                                            progress = prev_progress
                                            pct = progress.get('percentage', 0)
                                            if pct >= 99: status = 'ran'
                                            else: status = 'due'
                                            today_label = f"Last ({d_str[-5:]})" # e.g. Last (12-18)
                                            break
                                except: continue
                        
                        # Fallback to schedule logic if still 0% progress
                        if status == '' and schedule:
                            try:
                                hh, mm = (int(x) for x in schedule.split(':'))
                                scheduled_dt = datetime.datetime.combine(now.date(), datetime.time(hour=hh, minute=mm))
                                # If we have legacy last_run_dt but no progress data (rare case now), check it
                                if last_run_dt and last_run_dt >= scheduled_dt:
                                    status = 'ran'
                                else:
                                    if scheduled_dt <= now:
                                        status = 'due'
                                    else:
                                        status = 'pending'
                            except Exception:
                                status = ''

                    # Determine stats for display: prefer today's, otherwise latest
                    display_stats = progress if progress else {}
                    if not display_stats or (display_stats.get('balance', 0) == 0 and display_stats.get('income', 0) == 0):
                         dp = it.get('daily_progress', {})
                         if dp:
                             sorted_dates = sorted(dp.keys(), reverse=True)
                             for d in sorted_dates:
                                 if dp[d].get('balance', 0) > 0 or dp[d].get('income', 0) > 0:
                                     display_stats = dp[d]
                                     break
                             if not display_stats or (display_stats.get('balance', 0) == 0 and display_stats.get('income', 0) == 0):
                                 display_stats = dp[sorted_dates[0]]

                    # Pre-transform daily_progress for display (Apply 10% tax on historical withdrawal)
                    dp_raw = it.get('daily_progress', {})
                    dp_display = {}
                    for d_key, d_val in dp_raw.items():
                        new_val = d_val.copy()
                        if 'withdrawal' in new_val:
                            new_val['withdrawal'] = new_val['withdrawal'] * 0.9
                        dp_display[d_key] = new_val

                    # Update display_stats to use the net withdrawal
                    net_stats = display_stats.copy()
                    if 'withdrawal' in net_stats:
                        net_stats['withdrawal'] = net_stats['withdrawal'] * 0.9

                    saved_accounts.append({
                        "phone_display": display, 
                        "password": pwd, 
                        "level": lvl, 
                        "schedule": schedule, 
                        "last_run_ts": last_run_ts or it.get('last_run'), 
                        "last_sync_ts": it.get('last_sync_ts'),
                        "is_syncing": (
                            it.get('is_syncing', False) and 
                            it.get('sync_start_ts') and 
                            (now - datetime.datetime.fromisoformat(it['sync_start_ts'])).total_seconds() < 300
                            # Only consider syncing if started < 5 mins ago
                        ) if it.get('sync_start_ts') else False,
                        "sync_start_ts": it.get('sync_start_ts'),
                        "status": status,
                        "daily_progress": dp_display,
                        "display_stats": net_stats,
                        "today_label": today_label
                    })
    except Exception:
        saved_accounts = []

    # headless checkbox default value for GET UI: env var or True
    def parse_env_bool(v):
        if v is None:
            return None
        return str(v).strip().lower() in ("1","true","yes","on")

    env_headless = parse_env_bool(os.getenv('MBA_HEADLESS'))
    headless_default = True if env_headless is None else bool(env_headless)

    # Load settings to pass to template
    settings = data_manager.load_settings()

    return render_template(
        "index.html",
        saved=saved_accounts,
        now=now,
        settings=settings,
        queue_size=JOB_QUEUE.qsize()
    )



def _trigger_run_for_account(acc):
    # acc is the stored account dict with 'phone' normalized (starts with 62)
    phone_norm = acc.get('phone')
    if not phone_norm:
        return False
    # build display phone (without +62) as UI/CLI expects
    phone_display = phone_norm[2:] if phone_norm.startswith('62') else phone_norm
    pwd = acc.get('password', '')
    if not pwd:
        # skip accounts without password
        logger.info("SKIP %s: missing password", phone_norm)
        return False

    lvl = acc.get('level', 'E2')
    iterations = 30
    lvl_up = (lvl or '').upper()
    if lvl_up == 'E1':
        iterations = 15
    elif lvl_up == 'E2':
        iterations = 30
    elif lvl_up == 'E3':
        iterations = 60
    else:
        try:
            iterations = int(lvl)
        except Exception:
            iterations = 30

    # determine today's review text — no reviews on Sunday
    review_text = None
    r = acc.get('reviews', {}) or {}
    wk = ['mon','tue','wed','thu','fri','sat']
    try:
        wd = datetime.datetime.now().weekday()
        if wd < len(wk):
            key = wk[wd]
            review_text = r.get(key) or None
        else:
            review_text = None
    except Exception:
        review_text = None

    cmd = [sys.executable, "-m", "mba_automation.cli", "--phone", phone_display, "--password", pwd, "--iterations", str(iterations)]
    if review_text:
        cmd.extend(["--review", review_text])

    # run headless by default for scheduled runs
    cmd.append("--headless")

    logger.info("SCHEDULED ENQUEUE for %s: %s", phone_display, ' '.join(shlex.quote(c) for c in cmd))

    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Generate log filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"schedule_{phone_display}_{timestamp}.log")

    try:
        JOB_QUEUE.put({
            'cmd': cmd,
            'log_file': log_file,
            'phone_display': phone_display,
            'is_sync': False
        })
        logger.info("Queued scheduled job logging to %s", log_file)
        return True
    except Exception as e:
        logger.exception("FAILED SCHEDULED ENQUEUE for %s: %s", phone_display, e)
        return False



def _scheduler_loop():
    # Loop forever checking schedules and triggering runs when needed.
    while True:
        try:
            # do not run scheduled jobs on Sundays (weekday == 6)
            if datetime.datetime.now().weekday() == 6:
                time.sleep(SCHED_CHECK_INTERVAL)
                continue
            
            def check_and_trigger(accounts):
                now = datetime.datetime.now()
                any_triggered = False

                for acc in accounts:
                    sched = acc.get('schedule')
                    if not sched:
                        continue

                    # Current status skipping: don't trigger if already syncing/queued if possible
                    if acc.get('is_syncing'):
                        continue

                    # Parse schedule
                    try:
                        hh, mm = (int(x) for x in sched.split(':'))
                        # Today's scheduled time
                        scheduled_dt = datetime.datetime.combine(now.date(), datetime.time(hh, mm))
                    except Exception:
                        logger.warning("Invalid schedule format for %s: %s", acc.get('phone', 'unknown'), sched)
                        continue
                    
                    # CATCH-UP LOGIC: trigger if now >= scheduled_time AND hasn't run yet today
                    if now < scheduled_dt:
                        continue
                        
                    # Check last run
                    last_ts = acc.get('last_run_ts')
                    last_dt = None
                    if last_ts:
                         try: last_dt = datetime.datetime.fromisoformat(last_ts)
                         except: pass
                    elif acc.get('last_run'):
                         # legacy
                         try:
                             d = datetime.date.fromisoformat(acc.get('last_run'))
                             last_dt = datetime.datetime.combine(d, datetime.time(0,0))
                         except: pass

                    if last_dt:
                        # Prevent double triggering: skip if last run was after today's scheduled time
                         if last_dt >= scheduled_dt - datetime.timedelta(seconds=10):
                             continue
                        
                    # Trigger
                    ok = _trigger_run_for_account(acc)
                    if ok:
                        # Mark as triggered immediately to prevent double-queuing
                        acc['last_run_ts'] = datetime.datetime.now().isoformat()
                        if 'last_run' in acc: del acc['last_run']
                        any_triggered = True
                
                return accounts

            # 1. Peek first to avoid unnecessary locks
            peek_accounts = data_manager.load_accounts()
            needs_update = False
            now = datetime.datetime.now()
            
            for acc in peek_accounts:
                sched = acc.get('schedule')
                if not sched or acc.get('is_syncing'): 
                    continue
                try:
                    hh, mm = (int(x) for x in sched.split(':'))
                    scheduled_dt = datetime.datetime.combine(now.date(), datetime.time(hh, mm))
                    if now >= scheduled_dt:
                        # Check last run
                        last_ts = acc.get('last_run_ts')
                        if not last_ts:
                            needs_update = True
                            break
                        last_dt = datetime.datetime.fromisoformat(last_ts)
                        if last_dt < scheduled_dt - datetime.timedelta(seconds=10):
                            needs_update = True
                            break
                except: continue
            
            if needs_update:
                # 2. Run atomic update
                data_manager.atomic_update_accounts(check_and_trigger)

        except Exception as e:
            logger.exception("Scheduler error: %s", e)
 
        time.sleep(SCHED_CHECK_INTERVAL)


@app.route("/review", methods=["GET", "POST"])
def review():
    # phone passed as display (without leading 62) or full digits
    if request.method == 'POST':
        display_phone = request.form.get('phone', '').strip()
        if not display_phone:
            flash('Nomor HP tidak ditemukan pada form.', 'error')
            return redirect(url_for('index'))

        norm = normalize_phone(display_phone)
        # load accounts safely
        accounts = data_manager.load_accounts()

        # find account by normalized phone
        acc = None
        for a in accounts:
            if a.get('phone') == norm:
                acc = a
                break

        # collect reviews from form
        days_keys = ['mon','tue','wed','thu','fri','sat']
        reviews = {}
        for k in days_keys:
            reviews[k] = request.form.get(k, '').strip()

        if acc is None:
            # create account entry if missing
            acc = {'phone': norm, 'password': '', 'level': 'E2', 'reviews': reviews}
            accounts.append(acc)
        else:
            acc['reviews'] = reviews

        try:
            data_manager.write_accounts(accounts)
            flash('Review harian disimpan.', 'success')
        except Exception as e:
            flash(f'Gagal menyimpan review: {e}', 'error')

        return redirect(url_for('index'))

    # GET: show form
    display_phone = request.args.get('phone', '').strip()
    if not display_phone:
        flash('Masukkan nomor HP pada query string untuk mengedit review.', 'error')
        return redirect(url_for('index'))

    norm = normalize_phone(display_phone)
    existing = {}
    accounts = data_manager.load_accounts()
    for a in accounts:
        if a.get('phone') == norm:
            existing = a.get('reviews', {}) or {}
            break

    days = [('mon','Senin'),('tue','Selasa'),('wed','Rabu'),('thu','Kamis'),('fri','Jumat'),('sat','Sabtu')]
    return render_template('review.html', phone_display=display_phone, reviews=existing, days=days)


@app.route('/schedule', methods=['GET', 'POST'])
def schedule():
    if request.method == 'POST':
        display_phone = request.form.get('phone', '').strip()
        if not display_phone:
            flash('Nomor HP tidak ditemukan pada form.', 'error')
            return redirect(url_for('index'))

        norm = normalize_phone(display_phone)
        schedule_val = request.form.get('schedule', '').strip()

        # load accounts (locked)
        accounts = data_manager.load_accounts()

        # find account by normalized phone
        acc = None
        for a in accounts:
            if a.get('phone') == norm:
                acc = a
                break

        if acc is None:
            acc = {'phone': norm, 'password': '', 'level': 'E2'}
            accounts.append(acc)

        if schedule_val:
            # validate schedule format HH:MM
            m = re.fullmatch(r"(\d{1,2}):(\d{2})", schedule_val)
            if not m:
                flash('Format jadwal tidak valid, gunakan HH:MM mis. 08:30', 'error')
                return redirect(url_for('index'))
            hh = int(m.group(1))
            mm = int(m.group(2))
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                flash('Waktu jadwal di luar jangkauan (00:00-23:59).', 'error')
                return redirect(url_for('index'))

            acc['schedule'] = f"{hh:02d}:{mm:02d}"
        else:
            if 'schedule' in acc:
                del acc['schedule']

        try:
            data_manager.write_accounts(accounts)
            flash('Jadwal disimpan.', 'success')
        except Exception as e:
            flash(f'Gagal menyimpan jadwal: {e}', 'error')

        return redirect(url_for('index'))

    # GET
    display_phone = request.args.get('phone', '').strip()
    if not display_phone:
        flash('Masukkan nomor HP pada query string untuk mengatur jadwal.', 'error')
        return redirect(url_for('index'))

    norm = normalize_phone(display_phone)
    existing_schedule = ''
    accounts = data_manager.load_accounts()
    for a in accounts:
        if a.get('phone') == norm:
            existing_schedule = a.get('schedule', '') or ''
            break

    return render_template('schedule.html', phone_display=display_phone, schedule=existing_schedule)


@app.route("/history/<phone>/<metric>")
def history(phone, metric):
    # Normalize phone
    norm = normalize_phone(phone)
    accounts = data_manager.load_accounts()
    
    # Find account
    acc = next((a for a in accounts if a.get('phone') == norm), None)
    if not acc:
        flash("Akun tidak ditemukan", "error")
        return redirect(url_for('index'))
        
    daily_progress = acc.get('daily_progress', {})
    
    # Map metric to internal key and display label
    metric_map = {
        'modal': {'key': 'income', 'label': 'Modal'},
        'saldo': {'key': 'balance', 'label': 'Saldo'},
        'pendapatan': {'key': 'withdrawal', 'label': 'Pendapatan (Net)'}
    }
    
    if metric not in metric_map:
        flash("Tipe riwayat tidak valid", "error")
        return redirect(url_for('index'))
        
    info = metric_map[metric]
    target_key = info['key']
    label = info['label']
    
    # Prepare list
    history_items = []
    
    # Sort dates descending
    sorted_dates = sorted(daily_progress.keys(), reverse=True)
    
    # Locale for days
    days_id = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
    months_id = ['', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
    
    for date_str in sorted_dates:
        data = daily_progress[date_str]
        val = data.get(target_key)
        
        if val is not None:
             try:
                 dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                 day_name = days_id[dt.weekday()]
                 # Format: 14 Desember 2025
                 month_name = months_id[dt.month]
                 date_formatted = f"{dt.day} {month_name} {dt.year}"
                 # Apply 10% tax for Pendapatan metric
                 final_val = val
                 if metric == 'pendapatan':
                     final_val = float(val or 0) * 0.9
                 
                 history_items.append({
                     'date': date_str,
                     'date_formatted': date_formatted,
                     'day_name': day_name,
                     'value': final_val
                 })
             except Exception:
                 continue
                 
    return render_template('history.html', 
                           phone=phone, 
                           label=label, 
                           metric_type=metric,
                           history_items=history_items)


@app.route("/run_single", methods=["POST"])
def run_single():
    return _handle_single_run(request, sync_only=False)


@app.route("/sync_single", methods=["POST"])
def sync_single():
    return _handle_single_run(request, sync_only=True)


def _handle_single_run(req, sync_only=False):
    phone = req.form.get('phone', '').strip()
    if not phone:
        return jsonify({"ok": False, "msg": "No phone provided"}), 400

    norm = normalize_phone(phone)
    # find account to get password
    accounts = data_manager.load_accounts()
    acc = None
    for a in accounts:
        if a.get('phone') == norm:
            acc = a
            break
            
    if not acc:
         return jsonify({"ok": False, "msg": "Account not found"}), 404
         
    pwd = acc.get('password', '')
    if not pwd:
         return jsonify({"ok": False, "msg": "Password empty"}), 400

    # Determine iterations
    lvl = acc.get('level', 'E2')
    iterations = 30
    lvl_up = (lvl or '').upper()
    if lvl_up == 'E1':
        iterations = 15
    elif lvl_up == 'E2':
        iterations = 30
    elif lvl_up == 'E3':
        iterations = 60
    else:
        try:
            iterations = int(lvl)
        except Exception:
            iterations = 30

    phone_display = phone # already stripped in form
    
    cmd = [sys.executable, "-m", "mba_automation.cli", "--phone", phone_display, "--password", pwd, "--iterations", str(iterations)]
    
    # Always headless for single run unless valid reason not to? 
    # Actually, for debugging user might want headful single run.
    # But usually webapp triggers headless. Let's respect env/default.
    env_headless = os.getenv('MBA_HEADLESS')
    def parse_bool(v):
        if v is None:
            return None
        return str(v).strip().lower() in ("1","true","yes","on")
    h_val = parse_bool(env_headless)
    headless = True if h_val is None else h_val
    
    if headless:
        cmd.append("--headless")
        
    if sync_only:
        cmd.append("--sync")

    logger.info("SINGLE RUN ENQUEUE (Sync=%s) for %s: %s", sync_only, phone, ' '.join(shlex.quote(c) for c in cmd))

    try:
        # Create logs directory
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "sync" if sync_only else "manual"
        log_file = os.path.join(log_dir, f"{prefix}_{phone_display}_{timestamp}.log")
        
        # If running sync, mark state in accounts.json for UI persistence
        if sync_only:
            try:
                acc_list: List[Dict[str, Any]] = data_manager.load_accounts()
                changed = False
                for acc in acc_list:
                    # Normalize both sides to match
                    p1 = normalize_phone(str(acc.get('phone')))
                    p2 = normalize_phone(phone_display)
                    if p1 == p2:
                        acc['is_syncing'] = True
                        acc['sync_start_ts'] = datetime.datetime.now().isoformat()
                        changed = True
                        break
                if changed:
                    data_manager.write_accounts(acc_list)
            except Exception as e:
                logger.warning("Failed to mark sync state: %s", e)

        JOB_QUEUE.put({
            'cmd': cmd,
            'log_file': log_file,
            'phone_display': phone_display,
            'is_sync': sync_only
        })
        
        return jsonify({"ok": True, "msg": "Job queued"})
    except Exception as e:
        logger.exception("FAILED SINGLE RUN ENQUEUE: %s", e)
        return jsonify({"ok": False, "msg": str(e)}), 500





@app.route("/estimation")
def estimation_page():
    """Render the dedicated estimation page."""
    accounts = data_manager.load_accounts()
    
    # Filter by phone if provided (to fix "masih semuanya" complaint)
    phone_filter = request.args.get('phone')
    current_user = session.get('user_id')
    
    results = []
    for acc in accounts:
        # Implicitly filter by owner
        if acc.get('owner', 'admin') != current_user:
            continue
            
        phone = acc.get("phone", "")
        # Apply filter if set
        if phone_filter and phone_filter not in phone:
            continue

        # Get latest stats
        dp = acc.get('daily_progress', {})
        display_stats = {}
        if dp:
            sorted_dates = sorted(dp.keys(), reverse=True)
            for d in sorted_dates:
                if dp[d].get('balance', 0) > 0 or dp[d].get('income', 0) > 0:
                    display_stats = dp[d]
                    break
        
        income = display_stats.get('income', 0)
        balance = display_stats.get('balance', 0)
        level = acc.get('level')
        
        est_data = calculate_estimation(income, balance, level)
        
        results.append({
            "phone_display": phone_display(phone),
            "level": level or "Unknown",
            "income": income,
            "balance": balance,
            "estimation": est_data
        })
    
    return render_template('estimation.html', accounts=results, filter=phone_filter)


@app.route("/logs")
def view_logs():
    """Display automation logs from runs.log file."""
    lines = []
    if os.path.exists(LOG_FILE):
        try:
            # Read last 1000 lines
            with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
                lines = all_lines[-1000:]  # Last 1000 lines
        except Exception as e:
            flash(f"Error reading log file: {e}", "error")
    
    # Parse lines into structured format
    parsed_logs = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Parse format: "2025-11-29 23:00:00 INFO message"
        parts = line.split(' ', 3)
        if len(parts) >= 4:
            date = parts[0]
            time_str = parts[1]
            level = parts[2]
            message = parts[3] if len(parts) > 3 else ''
            parsed_logs.append({
                'timestamp': f"{date} {time_str}",
                'level': level,
                'message': message
            })
        else:
            # Fallback for unparsed lines
            parsed_logs.append({
                'timestamp': '',
                'level': 'UNKNOWN',
                'message': line
            })
    
    # Reverse for newest first
    parsed_logs.reverse()
    
    return render_template('logs.html', logs=parsed_logs, total=len(parsed_logs))


@app.route("/api/logs")
def api_logs():
    """API endpoint to fetch logs as JSON."""
    level_filter = request.args.get('level', '').upper()
    limit = int(request.args.get('limit', 100))
    
    lines = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[-limit:]
        except Exception:
            pass
    
    # Parse lines
    parsed_logs = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        parts = line.split(' ', 3)
        if len(parts) >= 4:
            date = parts[0]
            time_str = parts[1]
            level = parts[2]
            message = parts[3] if len(parts) > 3 else ''
            
            # Filter by level if specified
            if level_filter and level != level_filter:
                continue
            
            parsed_logs.append({
                'timestamp': f"{date} {time_str}",
                'level': level,
                'message': message
            })
    
    # Reverse for newest first
    parsed_logs.reverse()
    
    return jsonify({'logs': parsed_logs, 'total': len(parsed_logs)})


# ================= BACKGROUND THREADS STARTUP =================
# We start threads at module level but check if already running 
# to ensure they work both in 'python webapp.py' and 'gunicorn'.
def _start_background_threads():
    # Only start if not already started (useful for some dev servers)
    if not getattr(app, '_threads_started', False):
        # 1. Start worker thread (processes the JOB_QUEUE)
        # (Worker thread is actually started at line 60-61, which is fine)
        
        # 2. Start scheduler thread (checks schedules in accounts.json)
        # Only start scheduler if we are not in a debug reloader child or if explicitly told to
        if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            t_sched = threading.Thread(target=_scheduler_loop, daemon=True)
            t_sched.start()
            logger.info("Background scheduler thread started.")
        
        app._threads_started = True

# Trigger startup
_start_background_threads()


if __name__ == "__main__":
    # Development server only. For production, use gunicorn.
    app.run(host="0.0.0.0", port=5000, debug=True)

