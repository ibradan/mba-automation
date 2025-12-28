# MBA7 Playwright Automation (Termux Focus)

This project is optimized for running automation tasks directly on Android using **Termux**. It provides a web UI and a CLI for managing and executing automation scripts.

## Termux Quick Start

The easiest way to get started is to use the provided setup script:

```bash
chmod +x setup-termux.sh
./setup-termux.sh
```

### Running the Web UI

To start the dashboard:

```bash
source .venv/bin/activate
python webapp.py
```

Access the UI at: `http://localhost:5000` (from your phone) or `http://<PHONE_IP>:5000` (from other devices on the same network).

### Running in Background

To prevent Android from killing the automation when you close the app:
1. Run `termux-wake-lock` in a Termux session.
2. Disable battery optimization for Termux in your Android settings.
3. For persistent background services, consider using `termux-services`.

---

## CLI Usage

Run the CLI directly for specific accounts:

```bash
# single phone
python -m mba_automation.cli --phone 82129002163 --password "YOUR_PASSWORD"

# multiple phones
python -m mba_automation.cli --phones 82129002163,82211223344 --password "YOUR_PASSWORD"
```

---

## Configuration

- `accounts.json`: Stores account credentials and status.
- `settings.json`: Application settings (headless mode, telegram bot, etc.).
- `logs/`: Individual execution logs for each phone number.

## Technical Notes

- **Robustness**: Account file reads and writes are protected with locks and use atomic writes.
- **Headless Mode**: Defaults to headless. Override with `MBA_HEADLESS=0` or `--no-headless`.
- **Sunday Holiday**: Scheduled runs do NOT execute on Sundays.

---

## Legacy Documentation

Documentation for Raspberry Pi and VPS deployment has been moved to the `legacy/` directory.
