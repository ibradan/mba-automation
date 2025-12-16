from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
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


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "please-change-this")

LOG_FILE = os.path.join(os.path.dirname(__file__), "runs.log")
ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "accounts.json")
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
SCHED_LOCK = threading.Lock()
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
SCHED_LOCK = threading.Lock()
SCHED_CHECK_INTERVAL = 20  # seconds between schedule checks

# Job Queue for Serial Execution (Pi Zero Optimization)
JOB_QUEUE = queue.Queue()

def worker():
    """Background worker to process automation jobs serially."""
    while True:
        try:
            job = JOB_QUEUE.get()
            if job is None:
                break
            
            cmd = job.get('cmd')
            log_file = job.get('log_file')
            phone_display = job.get('phone_display')
            
            logger.info(f"QUEUE: Starting job for {phone_display}")
            
            try:
                # Open file for writing
                with open(log_file, "w") as f:
                    # Run synchronously - creating a BLOCKING call here
                    # This ensures only one browser instance runs at a time
                    subprocess.run(cmd, cwd=os.path.dirname(__file__), stdout=f, stderr=subprocess.STDOUT)
                
                logger.info(f"QUEUE: Finished job for {phone_display}")
            except Exception as e:
                logger.exception(f"QUEUE: Job failed for {phone_display}: {e}")
            finally:
                JOB_QUEUE.task_done()
                
        except Exception as e:
            logger.exception(f"Worker exception: {e}")

# Start worker thread
worker_thread = threading.Thread(target=worker, daemon=True)
worker_thread.start()



def _safe_load_settings():
    """Load settings from JSON file with error handling."""
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        return {}


def _safe_save_settings(settings):
    """Save settings to JSON file with error handling."""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        return False


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


@app.route("/settings/get", methods=["GET"])
def get_settings():
    return jsonify(_safe_load_settings())


@app.route("/settings/save", methods=["POST"])
def save_settings():
    try:
        data = request.get_json()
        if _safe_save_settings(data):
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "Failed to save settings"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/export_accounts", methods=["GET"])
def export_accounts():
    try:
        if os.path.exists(ACCOUNTS_FILE):
            return subprocess.check_output(['cat', ACCOUNTS_FILE]), 200, {
                'Content-Type': 'application/json',
                'Content-Disposition': 'attachment; filename=accounts.json'
            }
        return jsonify({"status": "error", "message": "No accounts file found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/import_accounts", methods=["POST"])
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
                _safe_write_accounts(data)
                return jsonify({"status": "success", "message": f"Imported {len(data)} accounts"})
            except json.JSONDecodeError:
                return jsonify({"status": "error", "message": "Invalid JSON file"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/", methods=["GET", "POST"])
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
                # load existing accounts to preserve reviews using locked read
                existing = {}
                raw_existing = _safe_load_accounts()
                for a in raw_existing:
                    existing[a.get('phone')] = a

                saved = []
                for phone, pwd, lvl in entries:
                    norm = normalize_phone(phone)
                    acc = {"phone": norm, "password": pwd, "level": (lvl or "E2")}
                    # merge reviews if present in existing data
                    if norm in existing and isinstance(existing[norm].get('reviews'), dict):
                        acc['reviews'] = existing[norm].get('reviews')
                    # merge schedule if present
                    if norm in existing and existing[norm].get('schedule'):
                        acc['schedule'] = existing[norm].get('schedule')
                    # CRITICAL FIX: preserve last_run timestamp to maintain status
                    if norm in existing and existing[norm].get('last_run'):
                        acc['last_run'] = existing[norm].get('last_run')
                    # CRITICAL FIX: preserve daily_progress to maintain tracking data
                    if norm in existing and existing[norm].get('daily_progress'):
                        acc['daily_progress'] = existing[norm].get('daily_progress')
                    saved.append(acc)
                # persist using locked, atomic write
                _safe_write_accounts(saved)
                flash(f"{len(saved)} akun disimpan.", "success")
            except Exception as e:
                flash(f"Gagal menyimpan akun: {e}", "error")
            return redirect(url_for("index"))

        # Only run automation if explicitly requested
        if action == 'start':
            # load saved accounts to read per-account reviews (if any)
            saved_accounts = _safe_load_accounts()

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

                # Load settings
                settings = _safe_load_settings()
                timeout = settings.get('timeout', 30)
                viewport = settings.get('viewport', 'iPhone 12')

                cmd = [sys.executable, "-m", "mba_automation.cli", "--phone", phone_for_cli, "--password", pwd, "--iterations", str(iterations), "--timeout", str(timeout), "--viewport", viewport]
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
                        'phone_display': phone
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
            try:
                # load existing accounts to preserve reviews via locked read
                existing = {}
                raw_existing = _safe_load_accounts()
                for a in raw_existing:
                    existing[a.get('phone')] = a

                saved = []
                for phone, pwd, lvl in entries:
                    norm = normalize_phone(phone)
                    acc = {"phone": norm, "password": pwd, "level": (lvl or "E2")}
                    if norm in existing and isinstance(existing[norm].get('reviews'), dict):
                        acc['reviews'] = existing[norm].get('reviews')
                    if norm in existing and existing[norm].get('schedule'):
                        acc['schedule'] = existing[norm].get('schedule')
                    # CRITICAL FIX: preserve last_run and daily_progress in run block too
                    if norm in existing and existing[norm].get('last_run'):
                        acc['last_run'] = existing[norm].get('last_run')
                    if norm in existing and existing[norm].get('daily_progress'):
                        acc['daily_progress'] = existing[norm].get('daily_progress')
                    saved.append(acc)
                _safe_write_accounts(saved)
            except Exception as e:
                # don't fail the request if saving fails
                logger.warning("WARNING saving accounts failed: %s", e)

        return redirect(url_for("index"))

    # GET: load saved accounts to prefill the form
    saved_accounts = []
    raw = _safe_load_accounts()
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
                    
                    if pct >= 100:
                        status = 'ran'
                    elif pct > 0:
                        status = 'due'  # Partial progress shows as yellow/due
                    else:
                        # Fallback to schedule logic if 0% progress
                        if schedule:
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
                    display_stats = {}
                    if pct > 0: # simplified check: if we have progress, we have data for today
                        display_stats = progress
                    elif progress: # or if progress exists but pct is 0 (started but low progress?)
                        display_stats = progress
                    else:
                        # Check past data in daily_progress
                        # daily_progress keys are YYYY-MM-DD
                        dp = it.get('daily_progress', {})
                        if dp:
                            # sort dates descending
                            sorted_dates = sorted(dp.keys(), reverse=True)
                            # pick the first one
                            latest_date = sorted_dates[0]
                            display_stats = dp[latest_date]

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
                        "daily_progress": it.get('daily_progress', {}),
                        "display_stats": display_stats
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
    settings = _safe_load_settings()

    return render_template(
        "index.html",
        saved=saved_accounts,
        now=now,
        settings=settings,
        queue_size=JOB_QUEUE.qsize()
    )



def _safe_load_accounts():
    with SCHED_LOCK:
        if os.path.exists(ACCOUNTS_FILE):
            try:
                with open(ACCOUNTS_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                # file corrupted or unreadable -> return empty list so callers can recover
                try:
                    # log the problem to the log file if possible
                    with open(LOG_FILE, 'a') as lf:
                        lf.write(f"{datetime.datetime.now().isoformat()} WARNING failed to read accounts file\n")
                except Exception:
                    pass
                return []
        return []


def _safe_write_accounts(accounts):
    with SCHED_LOCK:
        # atomic write to avoid partial files when concurrent readers exist
        tmp = ACCOUNTS_FILE + ".tmp"
        try:
            with open(tmp, 'w') as f:
                json.dump(accounts, f, indent=2)
            os.replace(tmp, ACCOUNTS_FILE)
        except Exception as e:
            # try best-effort logging
            logger.warning("WARNING failed to write accounts file: %s", e)


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
            'phone_display': phone_display
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
            now = datetime.datetime.now()
            now_hm = now.strftime('%H:%M')
            today_str = now.date().isoformat()

            accounts = _safe_load_accounts()
            modified = False
            for acc in accounts:
                sched = acc.get('schedule')
                if not sched:
                    continue

                # only check when the clock matches the scheduled H:M
                if sched != now_hm:
                    continue

                # Determine last run time. Prefer ISO timestamp 'last_run_ts'.
                last_ts = acc.get('last_run_ts')
                last_dt = None
                if last_ts:
                    try:
                        last_dt = datetime.datetime.fromisoformat(last_ts)
                    except Exception:
                        last_dt = None
                else:
                    # fallback for legacy 'last_run' date-only value: treat as that date at 00:00
                    legacy = acc.get('last_run')
                    if legacy:
                        try:
                            d = datetime.date.fromisoformat(legacy)
                            last_dt = datetime.datetime.combine(d, datetime.time(hour=0, minute=0))
                        except Exception:
                            last_dt = None

                # scheduled datetime for today at HH:MM
                try:
                    hh, mm = (int(x) for x in sched.split(':'))
                    scheduled_dt = datetime.datetime.combine(now.date(), datetime.time(hour=hh, minute=mm))
                except Exception:
                    # bad schedule format — skip
                    continue

                # If last_dt exists and is >= scheduled_dt, we've already run at/after the scheduled time — skip
                if last_dt is not None and last_dt >= scheduled_dt:
                    continue

                # Otherwise trigger the run
                ok = _trigger_run_for_account(acc)
                if ok:
                    # store full timestamp to allow precise comparisons later
                    acc['last_run_ts'] = datetime.datetime.now().isoformat()
                    # remove legacy field if present
                    if 'last_run' in acc:
                        try:
                            del acc['last_run']
                        except Exception:
                            pass
                    modified = True

            if modified:
                _safe_write_accounts(accounts)
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
        accounts = _safe_load_accounts()

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
            _safe_write_accounts(accounts)
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
    accounts = _safe_load_accounts()
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
        accounts = _safe_load_accounts()

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
            _safe_write_accounts(accounts)
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
    accounts = _safe_load_accounts()
    for a in accounts:
        if a.get('phone') == norm:
            existing_schedule = a.get('schedule', '') or ''
            break

    return render_template('schedule.html', phone_display=display_phone, schedule=existing_schedule)


@app.route("/history/<phone>/<metric>")
def history(phone, metric):
    # Normalize phone
    norm = normalize_phone(phone)
    accounts = _safe_load_accounts()
    
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
        'pendapatan': {'key': 'withdrawal', 'label': 'Pendapatan'}
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
                 
                 history_items.append({
                     'date_formatted': date_formatted,
                     'day_name': day_name,
                     'value': float(val)
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
    accounts = _safe_load_accounts()
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
    
    # Load settings
    settings = _safe_load_settings()
    timeout = settings.get('timeout', 30)
    viewport = settings.get('viewport', 'iPhone 12')
    
    cmd = [sys.executable, "-m", "mba_automation.cli", "--phone", phone_display, "--password", pwd, "--iterations", str(iterations), "--timeout", str(timeout), "--viewport", viewport]
    
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
                acc_list: List[Dict[str, Any]] = _safe_load_accounts()
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
                    _safe_write_accounts(acc_list)
            except Exception as e:
                logger.warning("Failed to mark sync state: %s", e)

        JOB_QUEUE.put({
            'cmd': cmd,
            'log_file': log_file,
            'phone_display': phone_display
        })
        
        return jsonify({"ok": True, "msg": "Job queued"})
    except Exception as e:
        logger.exception("FAILED SINGLE RUN ENQUEUE: %s", e)
        return jsonify({"ok": False, "msg": str(e)}), 500





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


# ================= BACKGROUND SCHEDULER THREAD =================
if __name__ == "__main__":
    # Development server only. For production, use gunicorn/uWSGI.
    # Start scheduler thread only when running the main process (avoid Werkzeug reloader double-start)
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        t = threading.Thread(target=_scheduler_loop, daemon=True)
        t.start()
        logger.info("Scheduler thread started.")

    app.run(host="0.0.0.0", port=5000, debug=True)

