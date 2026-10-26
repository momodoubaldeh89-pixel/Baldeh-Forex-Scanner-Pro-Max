# Baldeh Forex Scanner Pro Max — signal-quality and alert upgrades

## Included upgrades
1. **Stronger signal filtering and ranking:** the app highlights a stricter shortlist rather than treating every directional reading equally. The email job filters weaker directional signals and ranks the summary by signal quality and score.
2. **Entry / stop / target analysis:** forex levels use a daily ATR(14) estimate with a 1.5× ATR stop and 3× ATR target (illustrative 2:1 planned reward-to-risk). Stock levels use a 14-day mean absolute close change as a volatility proxy, not true-range ATR. All levels are estimates, not instructions or guarantees.
3. **Less email clutter:** each alert email summarizes at most 15 top-ranked qualifying new/changed signals and attaches `baldeh_full_signal_report.csv` with the full list for that run.

## Deploying updates into the existing GitHub repository
Replace these files in your existing repository with the versions in this package:
- `app.py`
- `hourly_email_alerts.py`
- `.github/workflows/hourly-email-alerts.yml`
- `UPGRADE_NOTES.md`

Keep `Baldeh_Forex_scanner.py`, `requirements.txt`, `signal_state.json`, and `EMAIL_ALERTS_SETUP.md` unless you intentionally want to replace them with the matching copies in this ZIP. Keep the three GitHub Actions secrets already configured: `GMAIL_SENDER`, `GMAIL_APP_PASSWORD`, and `ALERT_RECIPIENT`.

After committing the changed files, open **Actions → Baldeh Hourly Email Alert → Run workflow** to test. The email may only be sent when qualifying signals are new or their direction changes. The first run after replacing/resetting `signal_state.json` can send a larger CSV report, but the email body is capped at 15 candidates.

## Important limitations
- Hourly workflow runs do not make daily-candle data intraday/live. Forex and stock inputs are daily data from Yahoo Finance and may be delayed, missing, or different from broker quotes.
- Stock volatility levels use close-to-close changes because the current stock ranking feed is close-price based; they are not true high/low ATR.
- These are screening and planning estimates only. Verify prices, spreads, market hours, corporate events, news, and your broker's pip/contract value. The software does not place trades.
