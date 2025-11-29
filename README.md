# MBA7 Playwright Automation (Workspace)

This workspace contains the cleaned project for the MBA7 Playwright automation.

Follow the same setup as before:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install
```

Run the web UI:

```bash
python webapp.py

Run unit tests (added to validate phone helpers and account file IO):

```bash
source .venv/bin/activate
python -m unittest discover -s tests -p "test_*.py" -v
```

Notes about recent robustness improvements:
- Account file reads and writes are now protected with a lock and use atomic writes to avoid concurrent corruption.
- Routes that update accounts now use the safe helpers to avoid race conditions with the scheduler.
- Schedule input is validated (HH:MM, 00:00-23:59) before being saved.
- Background CLI runs now use a normalized display phone format consistently and Popen errors are logged instead of crashing requests.

Uploading to GitHub (private repository)
--------------------------------------

Before pushing to GitHub, make sure you do not accidentally commit secrets (passwords, accounts, logs). This project contains `accounts.json` and `runs.log` which may include sensitive data.

1) Recommended: use the provided helper (requires GitHub CLI `gh` and that you're authenticated):

```bash
# make sure gh is authenticated with your account
gh auth login

# create a private repo on your account and push everything in this folder
./scripts/create_private_repo.sh <repo-name> [--org <org-name>] [--description "desc"]
```

2) Manual approach using a private repo you create on github.com:

```bash
# create a new private repo on github.com (UI) and note the remote URL
# then run:
./scripts/manual_push.sh git@github.com:<you>/<repo>.git
```

3) Safety notes
- The repository's `.gitignore` already excludes `accounts.json` and `runs.log` by default. If you have already previously added these files to the git index, remove them before pushing:

```bash
git rm --cached accounts.json runs.log || true
git commit -m "chore: remove secrets from index" || true
```

```

Or run the CLI directly:

```bash
# single phone
python -m mba_automation.cli --phone 82129002163 --password "[REDACTED_PASSWORD]"

# multiple phones (repeat --phone or use --phones comma-separated)
python -m mba_automation.cli --phone 82129002163 --phone 82211223344 --password "[REDACTED_PASSWORD]"
python -m mba_automation.cli --phones 82129002163,82211223344 --password "[REDACTED_PASSWORD]"

Web UI note: the form supports multiple rows of inputs. Each row should include `NO HP`, `PASSWORD`, and `LEVEL` (jumlah tugas). The form sends `phone[]`, `password[]`, and `level[]` arrays and will start one background process per filled row.

Level mapping (used by the web UI):

- `E1` = 15 tugas
- `E2` = 30 tugas (default)
- `E3` = 60 tugas

Each row's `LEVEL` selects one of the above values; the web UI will pass the mapped tugas count to the CLI.

Headless behavior
-----------------

- Browsers now run in headless mode by default both for CLI and the Web UI (scheduled runs are always headless).
- Set environment variable `MBA_HEADLESS=0` (or `false`, `no`) to change default; CLI flags `--headless` and `--no-headless` can override the default.

Weekend / Sunday behaviour
--------------------------

- Sunday is considered a holiday: scheduled runs will NOT execute on Sundays and the review editor does not include Sunday (Minggu) anymore. Use schedules on Mon–Sat only.
```
