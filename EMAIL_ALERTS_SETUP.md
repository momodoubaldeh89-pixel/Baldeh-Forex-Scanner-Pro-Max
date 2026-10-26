# Gmail hourly alert setup

This adds a separate GitHub Actions scan that checks qualifying Forex and US-stock signals hourly and emails only when a symbol first qualifies or its qualifying direction changes. The Streamlit dashboard remains available as before. The scan uses daily Yahoo Finance candles, so checking hourly does **not** mean the underlying market data updates hourly.

## 1. Add these files to the root of the same GitHub repository as `app.py`

- `hourly_email_alerts.py`
- `.github/workflows/hourly-email-alerts.yml`
- `signal_state.json`

Keep `app.py`, `Baldeh_Forex_scanner.py`, and `requirements.txt` in the repository root. The workflow file must be inside `.github/workflows/`.

## 2. Create a Gmail App Password

1. Sign in to the Gmail account that will send alerts.
2. Turn on Google 2-Step Verification if it is not already enabled.
3. Open your Google Account security settings and create an **App Password** for this scanner. If Google does not offer App Passwords for your account, use an eligible Gmail account or another SMTP provider and update the script accordingly.
4. Do not use your normal Gmail password, and never paste the App Password into source code or this chat.

## 3. Add GitHub repository secrets

In your repository, open **Settings → Secrets and variables → Actions → New repository secret**. Add all three:

- `GMAIL_SENDER` — the Gmail address sending the alert emails.
- `GMAIL_APP_PASSWORD` — the Google App Password (spaces can be omitted).
- `ALERT_RECIPIENT` — the inbox where you want to receive alerts. This can be the same address or another address.

Secrets are configured in GitHub, not in Streamlit Community Cloud, because the hourly job runs in GitHub Actions.

## 4. Enable and test the workflow

1. Open the repository's **Actions** tab and enable workflows if GitHub prompts you.
2. Choose **Baldeh hourly email alerts** → **Run workflow** to test it manually.
3. Open that run and review its logs. If new qualifying signals exist, it sends an email; if none are new, no email is sent. On the first successful run, existing qualifying signals count as new and may trigger a first report.
4. Check that the workflow can push `signal_state.json` back to the repository. Repository Actions settings may need to allow read/write workflow permissions.

## How alerts work

- Forex bullish/bearish candidates use the scanner's EMA, RSI, momentum, and breakout checks.
- Stock candidates use the relative-strength scanner and trend conditions.
- The workflow checks once per hour (at minute 17), subject to GitHub Actions scheduling delays and usage limits.
- To reduce repeated messages, the workflow emails only when a symbol newly qualifies or its qualifying direction changes. It updates `signal_state.json` between runs.
- Yahoo Finance data is daily in this version. This is not a real-time broker feed, and alerts do not execute trades. Always verify signals and risk independently.


## Top-10 email behavior

The hourly job ranks qualifying Forex, US-stock, and commodity signals together using a rule-based quality score and emails only newly qualifying/changed entries that appear in the current top 10. If the top 10 has not changed, no email is sent. The score is a ranking aid, not a probability of profit.

## Updating an existing GitHub repository on mobile

1. Download and extract this ZIP.
2. In your repository, replace the root files `hourly_email_alerts.py`, `app.py`, `Baldeh_Forex_scanner.py`, `requirements.txt`, `README.md`, `EMAIL_ALERTS_SETUP.md`, and `signal_state.json` with the matching files from this ZIP.
3. Ensure the workflow file is uploaded at the exact path `.github/workflows/hourly-email-alerts.yml` (not in the repository root). GitHub does not show the workflow YAML in the root file list.
4. Keep the existing repository Actions secrets `GMAIL_SENDER`, `GMAIL_APP_PASSWORD`, and `ALERT_RECIPIENT`. Never put the Gmail App Password into a source file or commit.
5. Open **Actions → Baldeh hourly email alerts → Run workflow** to test. A successful workflow run confirms the script ran; a new email is sent only if there are newly qualifying/changed top-10 signals.
