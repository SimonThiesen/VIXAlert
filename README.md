# VIXAlert

Hourly GitHub Actions workflow that checks the CBOE Volatility Index (VIX) and sends a Telegram notification if it is greater than or equal to **35**.

## How it works

1. Workflow triggers every hour (top of the hour) via cron or manually via *Run Workflow*.
2. Python script `vix_alert.py` downloads the latest VIX data using `yfinance`.
3. Script prints a JSON payload to stdout and sets GitHub Action outputs (`vix_value`, `vix_exceeded`).
4. If `exceeded == true` the email step runs and sends an alert.

## GitHub Actions Workflow

Workflow file: `.github/workflows/vix-alert.yml`

It installs Python 3.11, dependencies from `requirements.txt`, runs the script, parses JSON with `jq`, and conditionally sends mail using `dawidd6/action-send-mail`.

## Required Secrets (Telegram)

| Secret | Description |
|--------|-------------|
| `TELEGRAM_TOKEN` | Bot token obtained from @BotFather |
| `TELEGRAM_CHAT_ID` | Numeric chat ID (your user ID or group ID).

Set these in repository Settings > Secrets and the workflow will send you a message when VIX >= 35.

## Optional Alternatives (If You Want More Channels)

You can still add GitHub Issues, Discord, Slack, or ntfy notifications—see previous revision history for examples. Currently only Telegram is active in the workflow.

## Local Testing

Create a virtual environment and run the script manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python vix_alert.py | jq '.'
```

Expected JSON keys: `timestamp`, `vix`, `threshold`, `exceeded`.

Exit codes:
* `0` success fetch
* `2` fetch error (script will include `error` in JSON)

## Adjusting Threshold

Edit `THRESHOLD` constant near top of `vix_alert.py`.

## Extending

Ideas:
* Add Slack or Teams webhook notifications.
* Store historical alerts in a GitHub issue or artifact.
* Add caching/backoff logic if data provider rate-limits.

## License

