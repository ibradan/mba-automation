Raspberry Pi deployment (systemd)

This document explains how to run the Flask web UI and its scheduler as a systemd service on a Raspberry Pi.

Assumptions
- Project is located at `/home/pi/projects/mba-automation-workspace` on the Pi (adjust paths if different).
- You will run the service as user `pi`. Change `User=` in the unit if you prefer another account.
- You will create a Python virtual environment in the project directory at `.venv`.

Steps

1) Copy project to Raspberry Pi

   Use git/rsync/scp to copy the workspace to the Pi, e.g.:

```bash
# from your laptop
scp -r /home/dan/projects/mba-automation-workspace pi@raspberrypi:/home/pi/projects/
```

2) Create and activate a virtual environment on the Pi

```bash
ssh pi@raspberrypi
cd /home/pi/projects/mba-automation-workspace
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# Install Playwright browsers (required for Playwright automation)
.venv/bin/python -m playwright install
```

3) Optional: create `.env` with secret (the unit references `EnvironmentFile`)

```bash
cat > .env <<'EOF'
FLASK_SECRET=please-change-this
# add other env var lines if needed
EOF
chmod 600 .env
```

4) Copy the systemd unit and enable service

```bash
# on the Pi
sudo cp deploy/mba-automation.service /etc/systemd/system/mba-automation.service
# make sure paths & User in the unit match your environment
sudo systemctl daemon-reload
sudo systemctl enable --now mba-automation.service
sudo systemctl status mba-automation.service
```

5) Logs and troubleshooting

- View the service log with journalctl:
```bash
sudo journalctl -u mba-automation.service -f
```
- The web UI should be available at `http://<raspberrypi-ip>:5000/` (default Flask dev server host/port used in `webapp.py`).

Notes & recommendations
- The unit runs the Flask dev server directly. For production or better concurrency, consider running via `gunicorn` or `uwsgi` behind `nginx`. For a Pi-run, the dev server is fine if you only need local access.
- Ensure system time and timezone are correct on the Pi (`timedatectl`), otherwise schedules will not match expected local times.
- If you prefer not to keep the web UI running, use a cron-wrapper approach (I can add that script if you want).
- To upgrade code: stop the service, pull new changes, update venv if needed, then `systemctl restart mba-automation.service`.

Safety
- Keep `.env` file permissions restricted (`chmod 600`).
- Do not expose port 5000 to the public internet unless you add authentication and TLS (use a reverse proxy + TLS).

If you want, I can also:
- Provide a `systemd` unit that runs via `gunicorn`.
- Add a small deploy script that automates venv creation, `playwright install`, copying unit, and enabling it.
