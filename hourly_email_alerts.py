"""Hourly signal-change email scanner for Baldeh_Forex Scanner Pro Max.
Runs in GitHub Actions, independent of the Streamlit web session.
"""
from __future__ import annotations
import json, os, smtplib, ssl, sys, io, csv
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path
import pandas as pd
import yfinance as yf
import Baldeh_Forex_scanner as base

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "signal_state.json"
FOREX_PAIRS = {
    "EUR/USD":"EURUSD=X", "GBP/USD":"GBPUSD=X", "USD/JPY":"JPY=X", "USD/CHF":"CHF=X",
    "AUD/USD":"AUDUSD=X", "NZD/USD":"NZDUSD=X", "USD/CAD":"CAD=X", "EUR/GBP":"EURGBP=X",
    "EUR/JPY":"EURJPY=X", "GBP/JPY":"GBPJPY=X", "AUD/JPY":"AUDJPY=X", "EUR/AUD":"EURAUD=X",
    "GBP/CHF":"GBPCHF=X", "USD/CNH":"CNH=X", "USD/SEK":"SEK=X", "USD/NOK":"NOK=X"
}


def scan_forex() -> list[dict]:
    raw = yf.download(list(FOREX_PAIRS.values()), period="1y", interval="1d", auto_adjust=True,
                      group_by="column", threads=True, progress=False)
    if raw is None or raw.empty:
        print("Forex data unavailable this run.")
        return []
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw.xs("Close", axis=1, level=-1)
    else:
        close = raw[["Close"]].rename(columns={"Close": list(FOREX_PAIRS.values())[0]})
    alerts = []
    for pair, ticker in FOREX_PAIRS.items():
        if ticker not in close.columns:
            continue
        s = close[ticker].dropna()
        if len(s) < 55:
            continue
        e20 = s.ewm(span=20, adjust=False).mean().iloc[-1]
        e50 = s.ewm(span=50, adjust=False).mean().iloc[-1]
        delta = s.diff(); gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, float("nan")); rsi_series = 100 - (100 / (1 + rs))
        rsi = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else 50.0
        last = float(s.iloc[-1]); momentum = float((s.iloc[-1] / s.iloc[-6] - 1) * 100)
        atr = float((s.diff().abs().rolling(14, min_periods=10).mean()).dropna().iloc[-1]) if len(s.diff().abs().rolling(14, min_periods=10).mean().dropna()) else float("nan")
        # Prefer OHLC true range when Yahoo provides high/low fields.
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                h = raw["High"][ticker].reindex(s.index); lo = raw["Low"][ticker].reindex(s.index); prev = s.shift(1)
                tr = pd.concat([(h-lo).abs(), (h-prev).abs(), (lo-prev).abs()], axis=1).max(axis=1)
                atr_series = tr.rolling(14, min_periods=10).mean().dropna()
                if not atr_series.empty: atr = float(atr_series.iloc[-1])
        except Exception:
            pass
        score = int(last > e20)*20 + int(last > e50)*25 + int(e20 > e50)*25
        score += 20 if 50 <= rsi <= 70 else (10 if rsi > 70 else 0)
        score += 10 if momentum > 0 else 0
        prior = s.iloc[-21:-1]
        if len(prior) >= 15 and last > float(prior.max()): score = min(100, score + 8)
        if len(prior) >= 15 and last < float(prior.min()): score = max(0, score - 8)
        signal = "BULLISH" if score >= 70 and last > e50 and rsi >= 50 else "BEARISH" if score <= 35 and last <= e50 and rsi < 50 else "MIXED"
        if signal in ("BULLISH", "BEARISH"):
            entry = last
            stop = entry - 1.5*atr if signal == "BULLISH" else entry + 1.5*atr
            target = entry + 3.0*atr if signal == "BULLISH" else entry - 3.0*atr
            alerts.append({"key": f"FX:{pair}", "asset": pair, "class": "Forex", "signal": signal,
                           "score": score, "price": last, "rsi": round(rsi, 1), "momentum_pct": round(momentum, 2),
                           "atr14": round(atr, 6) if pd.notna(atr) else "", "entry": round(entry, 6),
                           "stop": round(stop, 6) if pd.notna(atr) and atr > 0 else "",
                           "target": round(target, 6) if pd.notna(atr) and atr > 0 else "",
                           "risk_reward": 2.0 if pd.notna(atr) and atr > 0 else "",
                           "quality": "HIGH" if ((score >= 80 and 50 <= rsi <= 70) if signal == "BULLISH" else (score <= 20 and rsi < 50)) else "STANDARD",
                           "details": f"RSI {rsi:.1f}; 5-day momentum {momentum:+.2f}%"})
    return alerts


def scan_stocks() -> list[dict]:
    tickers = list(dict.fromkeys([base.BENCHMARK] + list(base.SECTORS.values()) +
                                 [t[2] for t in base.THEMES] + [t[0] for t in base.STOCKS]))
    prices = base.download_prices(tickers)
    if base.BENCHMARK not in prices:
        raise RuntimeError("SPY benchmark data unavailable")
    benchmark = prices[base.BENCHMARK]
    bench_returns = {label: base.total_return(benchmark, days) for label, days in base.TRADING_WINDOWS.items()}
    metrics = base.make_metrics(prices, [t[0] for t in base.STOCKS], bench_returns)
    alerts = []
    if metrics.empty: return alerts
    for _, row in metrics.iterrows():
        signal = str(row.get("Signal", ""))
        trend_points = int(row.get("Trend Points", 0))
        if signal in ("STRONG RS + UPTREND", "POSITIVE RS / TREND") and float(row.get("RS Score", 0)) >= 0.05:
            ticker = str(row["Ticker"]); series = prices[ticker].dropna() if ticker in prices else pd.Series(dtype=float)
            vol_series = series.diff().abs().rolling(14, min_periods=10).mean().dropna()
            vol = float(vol_series.iloc[-1]) if not vol_series.empty else float("nan")
            entry = float(row["Last Close"]); stop = entry-1.5*vol if pd.notna(vol) and vol>0 else ""; target = entry+3*vol if pd.notna(vol) and vol>0 else ""
            alerts.append({"key": f"STOCK:{ticker}", "asset": ticker, "class": "US Stock",
                           "signal": "BULLISH", "score": round(float(row["RS Score"])*100, 2), "price": entry,
                           "quality": "HIGH" if float(row.get("RS Score", 0)) >= 0.10 and trend_points >= 2 else "STANDARD",
                           "entry": round(entry, 4), "stop": round(stop, 4) if stop != "" else "", "target": round(target, 4) if target != "" else "", "risk_reward": 2.0 if stop != "" else "",
                           "details": f"{signal}; trend points {trend_points}/3; RS score {float(row['RS Score']):+.4f}; levels use 14-day mean absolute close change as volatility proxy"})
        elif signal == "WEAK RS / TREND" and not bool(row.get("Above 50D", True)) and not bool(row.get("Above 200D", True)):
            ticker = str(row["Ticker"]); series = prices[ticker].dropna() if ticker in prices else pd.Series(dtype=float)
            vol_series = series.diff().abs().rolling(14, min_periods=10).mean().dropna()
            vol = float(vol_series.iloc[-1]) if not vol_series.empty else float("nan")
            entry = float(row["Last Close"]); stop = entry+1.5*vol if pd.notna(vol) and vol>0 else ""; target = entry-3*vol if pd.notna(vol) and vol>0 else ""
            alerts.append({"key": f"STOCK:{ticker}", "asset": ticker, "class": "US Stock",
                           "signal": "BEARISH", "score": round(abs(float(row["RS Score"]))*100, 2), "price": entry,
                           "quality": "STANDARD", "entry": round(entry,4), "stop": round(stop,4) if stop != "" else "", "target": round(target,4) if target != "" else "", "risk_reward": 2.0 if stop != "" else "",
                           "details": "Weak relative strength; price below 50D and 200D moving averages; levels use 14-day mean absolute close change as volatility proxy"})
    return alerts


def send_email(new_alerts: list[dict]) -> None:
    sender = os.environ.get("GMAIL_SENDER", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    recipient = os.environ.get("ALERT_RECIPIENT", "").strip()
    missing = [name for name, value in [("GMAIL_SENDER", sender), ("GMAIL_APP_PASSWORD", password), ("ALERT_RECIPIENT", recipient)] if not value]
    if missing:
        raise RuntimeError("Missing GitHub Actions secrets: " + ", ".join(missing))
    now = datetime.now(timezone.utc).astimezone()
    # Put the strongest ranked candidates in the email body; include every new/changed qualifying signal in CSV.
    ranked = sorted(new_alerts, key=lambda x: (x.get("quality") == "HIGH", (float(x.get("score", 0)) if x.get("signal") == "BULLISH" else (100-float(x.get("score", 0)) if x.get("class") == "Forex" else float(x.get("score", 0))))), reverse=True)
    top = ranked[:15]
    lines = [f"Baldeh_Forex Scanner Pro Max — {len(new_alerts)} new/changed qualifying signal(s)",
             f"Checked: {now:%Y-%m-%d %H:%M %Z}",
             "Email summary shows up to 15 highest-ranked candidates. Full list is attached as CSV.",
             "Screening research only—not trade instructions or guarantees. Verify data, spreads, news, and risk.", ""]
    if not top:
        lines.append("No qualifying candidates to display.")
    for a in top:
        lines.extend([f"{a['signal']} | {a['class']} | {a['asset']} | {a.get('quality','STANDARD')} quality",
                      f"Score: {a['score']} | Latest price: {float(a['price']):.5f}",
                      f"Details: {a['details']}"])
        if a.get("stop") not in (None, "") and a.get("target") not in (None, ""):
            lines.append(f"Illustrative ATR levels: entry {a.get('entry')} | stop {a.get('stop')} | target {a.get('target')} | planned R:R {a.get('risk_reward')}:1")
        lines.append("")
    fields = ["class", "asset", "signal", "quality", "score", "price", "rsi", "momentum_pct", "atr14", "entry", "stop", "target", "risk_reward", "details"]
    csv_buffer = io.StringIO(); writer = csv.DictWriter(csv_buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for a in ranked:
        writer.writerow({k: a.get(k, "") for k in fields})
    msg = EmailMessage()
    msg["Subject"] = f"Baldeh Scanner: {len(new_alerts)} new/changed signals — top {min(15, len(top))}"
    msg["From"] = sender; msg["To"] = recipient; msg["Date"] = formatdate(localtime=True)
    msg.set_content("\n".join(lines))
    msg.add_attachment(csv_buffer.getvalue().encode("utf-8"), maintype="text", subtype="csv", filename="baldeh_full_signal_report.csv")
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as server:
        server.login(sender, password); server.send_message(msg)
    print(f"Sent ranked summary of up to 15 candidates plus CSV containing {len(ranked)} new/changed signals to configured recipient.")


def main() -> None:
    print("Running hourly email alert scan…")
    raw_alerts = scan_forex() + scan_stocks()
    # Quality filter: require a stronger forex score or meaningful positive stock relative strength.
    current_alerts = [a for a in raw_alerts if (a.get("class") == "Forex" and ((a.get("signal") == "BULLISH" and int(a.get("score", 0)) >= 75) or (a.get("signal") == "BEARISH" and int(a.get("score", 0)) <= 25)))
                      or (a.get("class") == "US Stock" and abs(float(a.get("score", 0))) >= 5.0)]
    current_state = {a["key"]: a["signal"] for a in current_alerts}
    try:
        previous_state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    except (json.JSONDecodeError, OSError):
        previous_state = {}
    new_alerts = [a for a in current_alerts if previous_state.get(a["key"]) != a["signal"]]
    # Update state even if there are no new alerts. GitHub Actions commits this file for the next run.
    STATE_PATH.write_text(json.dumps(current_state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Raw directional signals: {len(raw_alerts)}; qualifying after stronger-signal filter: {len(current_alerts)}; new/changed qualifying signals: {len(new_alerts)}")
    if new_alerts:
        send_email(new_alerts)
    else:
        print("No new or changed qualifying signals; no email sent.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Hourly alert scan failed: {exc}", file=sys.stderr)
        raise
