"""Hourly signal-change email scanner for stocks, Forex and commodities.
Runs in GitHub Actions. Signals are rule-based screening indicators, not trade advice.
"""
from __future__ import annotations
import json, os, smtplib, ssl, sys
from datetime import datetime, timezone
from email.message import EmailMessage
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
# Yahoo Finance futures continuous symbols. Availability varies by instrument and provider.
COMMODITIES = {
    "Gold":"GC=F", "Silver":"SI=F", "WTI Crude Oil":"CL=F", "Brent Crude Oil":"BZ=F",
    "Natural Gas":"NG=F", "Copper":"HG=F", "Corn":"ZC=F", "Wheat":"ZW=F",
    "Soybeans":"ZS=F", "Coffee":"KC=F", "Cotton":"CT=F", "Sugar":"SB=F"
}


def get_close(ticker: str, period: str, interval: str) -> pd.Series:
    raw = yf.download(ticker, period=period, interval=interval, auto_adjust=True,
                      group_by="column", threads=False, progress=False)
    if raw is None or raw.empty:
        return pd.Series(dtype=float)
    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            close = raw["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
        else:
            close = raw.xs("Close", axis=1, level=-1).iloc[:, 0]
    else:
        if "Close" not in raw.columns:
            return pd.Series(dtype=float)
        close = raw["Close"]
    return pd.to_numeric(close, errors="coerce").dropna().sort_index()


def evaluate_trend(series: pd.Series, asset: str, asset_class: str, timeframe: str, key_prefix: str) -> list[dict]:
    """Return a qualifying directional signal from EMA/RSI/momentum checks."""
    s = series.dropna()
    if len(s) < 55:
        return []
    ema20 = s.ewm(span=20, adjust=False).mean()
    ema50 = s.ewm(span=50, adjust=False).mean()
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi_series = 100 - (100 / (1 + rs))
    last = float(s.iloc[-1]); e20 = float(ema20.iloc[-1]); e50 = float(ema50.iloc[-1])
    rsi = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else 50.0
    lookback = 5 if timeframe == "Intraday (1h)" else 6
    momentum = float((s.iloc[-1] / s.iloc[-lookback] - 1) * 100)
    bullish_points = int(last > e20)*30 + int(e20 > e50)*30 + int(rsi >= 50)*20 + int(momentum > 0)*20
    bearish_points = int(last < e20)*30 + int(e20 < e50)*30 + int(rsi < 50)*20 + int(momentum < 0)*20
    if bullish_points >= 80 and last > e50 and rsi >= 50:
        signal, score = "BULLISH", bullish_points
    elif bearish_points >= 80 and last < e50 and rsi < 50:
        signal, score = "BEARISH", bearish_points
    else:
        return []
    # Cross-market quality score (0-100): trend alignment is the base,
    # with capped momentum and RSI confirmation bonuses. This is not a probability.
    momentum_bonus = min(abs(momentum) * 2.0, 10.0)
    rsi_bonus = min(abs(rsi - 50.0) * 0.5, 10.0)
    quality = min(100.0, 0.8 * score + momentum_bonus + rsi_bonus)
    return [{"key": f"{key_prefix}:{timeframe}:{asset}", "asset": asset, "class": asset_class,
             "timeframe": timeframe, "signal": signal, "score": score,
             "quality_score": round(quality, 2), "price": last,
             "details": f"EMA20 {'>' if e20 > e50 else '<'} EMA50; RSI {rsi:.1f}; momentum {momentum:+.2f}% over {lookback} bars"}]


def scan_fx_and_commodities() -> list[dict]:
    alerts: list[dict] = []
    instruments = [(name, ticker, "Forex", "FX") for name, ticker in FOREX_PAIRS.items()]
    instruments += [(name, ticker, "Commodity", "CMDTY") for name, ticker in COMMODITIES.items()]
    tickers = list(dict.fromkeys(ticker for _, ticker, _, _ in instruments))
    # Batch each timeframe into one Yahoo Finance request to reduce runtime and rate-limit risk.
    for label, period, interval in [("Intraday (1h)", "60d", "1h"), ("Swing (1d)", "1y", "1d")]:
        try:
            raw = yf.download(tickers, period=period, interval=interval, auto_adjust=True,
                              group_by="column", threads=True, progress=False)
            if raw is None or raw.empty:
                print(f"{label} Forex/commodity data unavailable this run.")
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                if "Close" in raw.columns.get_level_values(0):
                    close = raw["Close"]
                else:
                    close = raw.xs("Close", axis=1, level=-1)
            else:
                if "Close" not in raw.columns:
                    continue
                close = raw[["Close"]].rename(columns={"Close": tickers[0]})
            if isinstance(close, pd.Series):
                close = close.to_frame(name=tickers[0])
            for name, ticker, cls, prefix in instruments:
                if ticker not in close.columns:
                    continue
                try:
                    alerts.extend(evaluate_trend(close[ticker].dropna(), name, cls, label, prefix))
                except Exception as exc:
                    print(f"Skipping {cls} {name} {label}: {exc}")
        except Exception as exc:
            print(f"Could not fetch {label} Forex/commodity batch: {exc}")
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
        signal = str(row.get("Signal", "")); trend_points = int(row.get("Trend Points", 0))
        if signal in ("STRONG RS + UPTREND", "POSITIVE RS / TREND") and float(row.get("RS Score", 0)) >= 0.02:
            rs_strength = min(abs(float(row.get("RS Score", 0))) * 100.0, 35.0)
            quality = min(100.0, trend_points / 3.0 * 65.0 + rs_strength)
            alerts.append({"key": f"STOCK:{row['Ticker']}", "asset": str(row["Ticker"]), "class": "US Stock",
                           "timeframe": "Swing (daily)", "signal": "BULLISH", "score": round(float(row["RS Score"])*100, 2),
                           "quality_score": round(quality, 2), "price": float(row["Last Close"]),
                           "details": f"{signal}; trend points {trend_points}/3; RS score {float(row['RS Score']):+.4f}"})
        elif signal == "WEAK RS / TREND" and not bool(row.get("Above 50D", True)) and not bool(row.get("Above 200D", True)):
            rs_strength = min(abs(float(row.get("RS Score", 0))) * 100.0, 35.0)
            quality = min(100.0, trend_points / 3.0 * 65.0 + rs_strength)
            alerts.append({"key": f"STOCK:{row['Ticker']}", "asset": str(row["Ticker"]), "class": "US Stock",
                           "timeframe": "Swing (daily)", "signal": "BEARISH", "score": round(float(row["RS Score"])*100, 2),
                           "quality_score": round(quality, 2), "price": float(row["Last Close"]),
                           "details": "Weak relative strength; price below 50D and 200D averages"})
    return alerts


def send_email(new_alerts: list[dict]) -> None:
    # Final safety cap: never send more than 10 instruments in one email.
    new_alerts = sorted(new_alerts, key=lambda x: (x.get("quality_score", 0), x.get("score", 0)), reverse=True)[:10]
    if not new_alerts:
        print("No new alerts to email.")
        return
    sender = os.environ.get("GMAIL_SENDER", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    recipient = os.environ.get("ALERT_RECIPIENT", "").strip()
    missing = [name for name, value in [("GMAIL_SENDER", sender), ("GMAIL_APP_PASSWORD", password), ("ALERT_RECIPIENT", recipient)] if not value]
    if missing:
        raise RuntimeError("Missing GitHub Actions secrets: " + ", ".join(missing))
    now = datetime.now(timezone.utc).astimezone()
    lines = [f"Baldeh_Forex Scanner Pro Max — {len(new_alerts)} Top-10 signal(s) newly qualifying/changed",
             f"Checked: {now:%Y-%m-%d %H:%M %Z}", "",
             "Top 10 are ranked together across Forex, US stocks and commodities.",
             "Quality score (0-100) is a rule-based ranking, NOT a win probability.",
             "Intraday signals use 1-hour bars; swing signals use daily bars.",
             "These are screening alerts, not trade instructions. Data can be delayed or unavailable; verify prices and risk before acting.", ""]
    for rank, a in enumerate(new_alerts, start=1):
        lines.extend([f"#{rank} | {a['signal']} | {a['class']} | {a['asset']} | {a.get('timeframe', 'Swing')}",
                      f"Quality: {a.get('quality_score', 0):.1f}/100 | Raw score: {a['score']} | Latest price: {a['price']:.5f}",
                      f"Details: {a['details']}", ""])
    msg = EmailMessage(); msg["Subject"] = f"Baldeh Scanner: Top {len(new_alerts)} new/changed signal(s)"
    msg["From"] = sender; msg["To"] = recipient; msg.set_content("\n".join(lines))
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as server:
        server.login(sender, password); server.send_message(msg)
    print(f"Sent {len(new_alerts)} alert(s) to configured recipient.")


def main() -> None:
    print("Running hourly email scan: stocks + Forex + commodities; intraday + swing…")
    current_alerts = scan_fx_and_commodities() + scan_stocks()
    # One comparable cross-market ranking; never rank stock raw RS values against FX scores.
    ranked = sorted(current_alerts, key=lambda a: (a.get("quality_score", 0), a.get("score", 0)), reverse=True)
    top10 = ranked[:10]
    current_signals = {a["key"]: a["signal"] for a in current_alerts}
    try:
        stored = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    except (json.JSONDecodeError, OSError):
        stored = {}
    # Backward-compatible with the earlier flat {key: signal} state file.
    if isinstance(stored, dict) and "signals" in stored:
        previous_signals = stored.get("signals", {})
        previous_top10 = set(stored.get("top10", []))
    else:
        previous_signals = stored if isinstance(stored, dict) else {}
        previous_top10 = set()
    new_alerts = [a for a in top10 if previous_signals.get(a["key"]) != a["signal"] or a["key"] not in previous_top10]
    new_state = {"signals": current_signals, "top10": [a["key"] for a in top10]}
    STATE_PATH.write_text(json.dumps(new_state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Qualifying signals: {len(current_alerts)}; top-ranked: {len(top10)}; new/changed top-10: {len(new_alerts)}")
    if new_alerts: send_email(new_alerts)
    else: print("Top 10 unchanged; no email sent.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Hourly alert scan failed: {exc}", file=sys.stderr)
        raise
