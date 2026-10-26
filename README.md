# Baldeh_Forex Scanner Pro Max

Mobile-friendly Streamlit scanner combining Forex technical screening with US stock, sector, and theme relative-strength ranking.

## Included modules
- Smart opportunity ranking feed across Forex and US stocks
- Forex trend/momentum scanner (EMA20/EMA50, RSI(14), 5-session momentum, 20-session breakout)
- Stock, sector, and theme relative-strength rankings
- Market regime detector (SPY vs 50D/200D moving averages)
- In-app alert lists with CSV export
- Position risk calculator based on account risk and stop distance
- Green bullish, red bearish, yellow mixed signal colors
- Mobile-responsive layout and cached market data

## Deploy to Streamlit Community Cloud
1. Create a **new** GitHub repository, for example `Baldeh-Forex-Scanner-Pro-Max`. Keep your current working deployment unchanged while testing.
2. Upload `app.py`, `Baldeh_Forex_scanner.py`, `requirements.txt`, and `README.md` into the repository root (not inside a nested folder).
3. In Streamlit Community Cloud, create a new app from that repository. Set **Main file path** to `app.py`.
4. Wait for dependencies to install and check the app on mobile and desktop.
5. Once satisfied, you can decide whether to replace the original deployment.

## Important notes
- Forex prices come from Yahoo Finance and may be unavailable or differ from your broker.
- The scanner currently uses daily FX data. Intraday 4-hour feed availability is not guaranteed; the UI clearly notes this.
- Alerts are in-app scan results and CSV downloads, not background email/SMS/push notifications.
- The risk calculator estimates cash risk and pip distance, not broker-specific lots. Verify pip value and contract size before trading.
- This is an educational research tool, not financial advice, and it does not place trades.


## Hourly email alerts: stocks, Forex and commodities
The GitHub Actions workflow checks for newly qualifying or changed signals in US stocks, 16 Forex pairs, and selected commodity futures. Forex and commodities are evaluated on both 1-hour bars (intraday) and daily bars (swing). Stocks use the existing daily relative-strength/trend rules. Alerts are based on EMA20/EMA50, RSI, momentum, and the stock relative-strength model; instruments that do not meet the defined criteria are not emailed.

Commodity futures symbols include gold, silver, WTI and Brent crude, natural gas, copper, corn, wheat, soybeans, coffee, cotton and sugar where Yahoo Finance data is available. Futures are not the same as spot prices or ETFs, and data availability varies. Hourly workflow execution does not guarantee that market prices update every hour.

For Gmail configuration and GitHub Actions secrets, see `EMAIL_ALERTS_SETUP.md`.

## Top-10 cross-market email ranking (updated)

The hourly email workflow now ranks qualifying signals together across Forex, US stocks and commodities, then considers only the top 10. A rule-based Quality score from 0–100 is used to compare the different asset classes; it is a screening rank, not a probability of profit. Email is sent when a signal newly enters the top 10 or its direction changes while in the top 10. If the top 10 is unchanged, no email is sent, to avoid hourly inbox spam. Commodity futures and hourly data availability depend on Yahoo Finance.
