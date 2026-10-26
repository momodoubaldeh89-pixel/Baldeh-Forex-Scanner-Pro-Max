#!/usr/bin/env python3
"""
Baldeh_Forex scanner
Automatically refreshes US stock-market sector, theme, and stock relative-strength rankings.

Data source: Yahoo Finance via yfinance. Run again to fetch updated market data.
This is a research scanner, not a trading system or investment advice.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
    import yfinance as yf
except ImportError:
    print("Missing packages. Install with: pip install -r requirements.txt")
    sys.exit(1)

APP_NAME = "Baldeh_Forex_scanner"
OUT_DIR = Path(__file__).resolve().parent / "scanner_output"
OUT_DIR.mkdir(exist_ok=True)

# GICS sector ETFs (US-listed sector proxies).
SECTORS = {
    "Information Technology": "XLK",
    "Health Care": "XLV",
    "Financials": "XLF",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
}

# Theme proxies are ETFs, where available. Some ETFs overlap sectors by design.
THEMES = [
    ("Semiconductors", "Information Technology", "SOXX"),
    ("Cybersecurity", "Information Technology", "CIBR"),
    ("Cloud Computing", "Information Technology", "SKYY"),
    ("Software", "Information Technology", "IGV"),
    ("Artificial Intelligence & Robotics", "Information Technology", "BOTZ"),
    ("Quantum Computing", "Information Technology", "QTUM"),
    ("Biotechnology", "Health Care", "XBI"),
    ("Pharmaceuticals", "Health Care", "IHE"),
    ("Medical Devices", "Health Care", "IHI"),
    ("Healthcare Providers", "Health Care", "IHF"),
    ("Digital Payments", "Financials", "IPAY"),
    ("Regional Banks", "Financials", "KRE"),
    ("Insurance", "Financials", "KIE"),
    ("Consumer E-commerce", "Consumer Discretionary", "IBUY"),
    ("Autos & Electric Vehicles", "Consumer Discretionary", "DRIV"),
    ("Travel & Leisure", "Consumer Discretionary", "PEJ"),
    ("Consumer Staples", "Consumer Staples", "XLP"),
    ("Oil & Gas Exploration & Production", "Energy", "XOP"),
    ("Oil Services", "Energy", "OIH"),
    ("Clean Energy", "Energy", "ICLN"),
    ("Uranium & Nuclear", "Energy", "URA"),
    ("Aerospace & Defense", "Industrials", "ITA"),
    ("Industrial Automation & Robotics", "Industrials", "ROBO"),
    ("Transportation & Logistics", "Industrials", "IYT"),
    ("Copper Miners", "Materials", "COPX"),
    ("Gold Miners", "Materials", "GDX"),
    ("Lithium & Battery Materials", "Materials", "LIT"),
    ("Uranium Miners", "Materials", "URA"),
    ("Data-Center & Digital Infrastructure", "Real Estate", "SRVR"),
    ("REITs", "Real Estate", "VNQ"),
    ("Utilities", "Utilities", "XLU"),
    ("Solar Energy", "Utilities", "TAN"),
    ("Telecommunications", "Communication Services", "IYZ"),
    ("Media & Entertainment", "Communication Services", "PBS"),
    ("Social Media & Digital Advertising", "Communication Services", "SOCL"),
    ("Video Games & Esports", "Communication Services", "HERO"),
]

# Curated examples to compare inside sectors/themes. This is not an exhaustive universe.
# Format: (ticker, sector, theme)
STOCKS = [
    # Information Technology
    ("NVDA","Information Technology","AI & Semiconductors"), ("AMD","Information Technology","Semiconductors"),
    ("AVGO","Information Technology","Semiconductors"), ("QCOM","Information Technology","Semiconductors"),
    ("MU","Information Technology","Memory & Semiconductors"), ("TSM","Information Technology","Semiconductors"),
    ("MSFT","Information Technology","Cloud & Enterprise Software"), ("ORCL","Information Technology","Cloud & Enterprise Software"),
    ("CRM","Information Technology","Enterprise Software"), ("NOW","Information Technology","Enterprise Software"),
    ("DDOG","Information Technology","Cloud Monitoring"), ("PLTR","Information Technology","AI Software"),
    ("PANW","Information Technology","Cybersecurity"), ("CRWD","Information Technology","Cybersecurity"),
    ("NET","Information Technology","Cybersecurity & Infrastructure"), ("ZS","Information Technology","Cybersecurity"),
    ("FTNT","Information Technology","Cybersecurity"), ("SNPS","Information Technology","Chip Design Software"),
    # Health Care
    ("LLY","Health Care","Pharmaceuticals"), ("NVO","Health Care","Pharmaceuticals"),
    ("ABBV","Health Care","Pharmaceuticals"), ("MRK","Health Care","Pharmaceuticals"),
    ("AMGN","Health Care","Biotechnology"), ("REGN","Health Care","Biotechnology"),
    ("VRTX","Health Care","Biotechnology"), ("GILD","Health Care","Biotechnology"),
    ("ISRG","Health Care","Robotic Surgery"), ("ABT","Health Care","Medical Devices"),
    ("BSX","Health Care","Medical Devices"), ("DXCM","Health Care","Medical Devices"),
    ("UNH","Health Care","Healthcare Services"), ("HCA","Health Care","Hospitals"),
    # Financials
    ("JPM","Financials","Banking"), ("GS","Financials","Investment Banking"),
    ("MS","Financials","Investment Banking"), ("BAC","Financials","Banking"),
    ("V","Financials","Digital Payments"), ("MA","Financials","Digital Payments"),
    ("PYPL","Financials","Digital Payments"), ("XYZ","Financials","Digital Payments"),
    ("BLK","Financials","Asset Management"), ("KKR","Financials","Alternative Asset Management"),
    ("COIN","Financials","Crypto-Linked Financial Services"), ("CME","Financials","Exchanges"),
    # Consumer Discretionary
    ("AMZN","Consumer Discretionary","E-commerce"), ("TSLA","Consumer Discretionary","Electric Vehicles"),
    ("HD","Consumer Discretionary","Home Improvement"), ("LOW","Consumer Discretionary","Home Improvement"),
    ("NKE","Consumer Discretionary","Apparel & Footwear"), ("MCD","Consumer Discretionary","Restaurants"),
    ("BKNG","Consumer Discretionary","Travel"), ("ABNB","Consumer Discretionary","Travel"),
    ("DASH","Consumer Discretionary","Delivery Platforms"), ("TJX","Consumer Discretionary","Retail"),
    # Consumer Staples
    ("WMT","Consumer Staples","Retail & Grocery"), ("COST","Consumer Staples","Retail & Grocery"),
    ("PG","Consumer Staples","Household Products"), ("KO","Consumer Staples","Beverages"),
    ("PEP","Consumer Staples","Beverages & Snacks"), ("CL","Consumer Staples","Personal Care"),
    ("PM","Consumer Staples","Tobacco"), ("KHC","Consumer Staples","Packaged Food"),
    # Energy
    ("XOM","Energy","Integrated Oil & Gas"), ("CVX","Energy","Integrated Oil & Gas"),
    ("COP","Energy","Oil & Gas Production"), ("EOG","Energy","Oil & Gas Production"),
    ("OXY","Energy","Oil & Gas Production"), ("FANG","Energy","Oil & Gas Production"),
    ("SLB","Energy","Oilfield Services"), ("HAL","Energy","Oilfield Services"),
    ("FSLR","Energy","Solar Technology"), ("ENPH","Energy","Solar Technology"),
    ("CEG","Energy","Nuclear Power"), ("VST","Energy","Power Generation"),
    # Industrials
    ("GE","Industrials","Aerospace"), ("RTX","Industrials","Aerospace & Defense"),
    ("LMT","Industrials","Aerospace & Defense"), ("NOC","Industrials","Aerospace & Defense"),
    ("CAT","Industrials","Construction Equipment"), ("ETN","Industrials","Electrification"),
    ("HON","Industrials","Industrial Technology"), ("PH","Industrials","Industrial Components"),
    ("UPS","Industrials","Logistics"), ("UNP","Industrials","Railroads"),
    ("RKLB","Industrials","Space Economy"), ("JOBY","Industrials","Advanced Air Mobility"),
    # Materials
    ("FCX","Materials","Copper"), ("SCCO","Materials","Copper"),
    ("NEM","Materials","Gold Mining"), ("AEM","Materials","Gold Mining"),
    ("ALB","Materials","Lithium"), ("MP","Materials","Rare Earths"),
    ("NUE","Materials","Steel"), ("LIN","Materials","Industrial Gases"),
    ("CF","Materials","Fertilizers"), ("AA","Materials","Aluminum"),
    # Real Estate
    ("PLD","Real Estate","Industrial Warehouses"), ("EQIX","Real Estate","Data Centers"),
    ("DLR","Real Estate","Data Centers"), ("AMT","Real Estate","Cell Towers"),
    ("O","Real Estate","Net Lease REITs"), ("WELL","Real Estate","Healthcare REITs"),
    ("AVB","Real Estate","Apartments"), ("EXR","Real Estate","Self Storage"),
    # Utilities
    ("NEE","Utilities","Renewable Utilities"), ("DUK","Utilities","Electric Utilities"),
    ("SO","Utilities","Electric Utilities"), ("AEP","Utilities","Electric Grid"),
    ("CEG","Utilities","Nuclear Power"), ("TLN","Utilities","Power Generation"),
    ("AWK","Utilities","Water Utilities"), ("EXC","Utilities","Electric Utilities"),
    # Communication Services
    ("GOOGL","Communication Services","Search & Digital Advertising"),
    ("META","Communication Services","Social Media & Advertising"),
    ("NFLX","Communication Services","Streaming"), ("DIS","Communication Services","Media & Entertainment"),
    ("T","Communication Services","Telecommunications"), ("VZ","Communication Services","Telecommunications"),
    ("TMUS","Communication Services","Telecommunications"), ("SPOT","Communication Services","Music Streaming"),
    ("RBLX","Communication Services","Gaming Platforms"), ("TTWO","Communication Services","Video Games"),
]

BENCHMARK = "SPY"
TRADING_WINDOWS = {"1M": 21, "3M": 63, "6M": 126, "12M": 252}
WEIGHTS = {"1M": 0.20, "3M": 0.30, "6M": 0.30, "12M": 0.20}


def download_prices(tickers: list[str]) -> pd.DataFrame:
    """Download adjusted daily closes; yfinance auto-adjusts OHLC."""
    unique = list(dict.fromkeys(tickers))
    print(f"Downloading daily prices for {len(unique)} symbols from Yahoo Finance...")
    raw = yf.download(
        tickers=unique,
        period="2y",
        interval="1d",
        auto_adjust=True,
        group_by="column",
        threads=True,
        progress=False,
    )
    if raw is None or raw.empty:
        raise RuntimeError("No price data returned. Check internet access or try again later.")
    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            prices = raw["Close"].copy()
        else:
            # Fallback for alternate yfinance column ordering
            prices = raw.xs("Close", axis=1, level=-1)
    else:
        # Single ticker response
        if "Close" not in raw.columns:
            raise RuntimeError("Yahoo Finance response did not contain closing prices.")
        prices = raw[["Close"]].rename(columns={"Close": unique[0]})
    if isinstance(prices, pd.Series):
        prices = prices.to_frame(name=unique[0])
    prices.columns = [str(c) for c in prices.columns]
    prices = prices.sort_index().ffill()
    return prices


def total_return(series: pd.Series, days: int) -> float:
    s = series.dropna()
    if len(s) <= days:
        return np.nan
    return float(s.iloc[-1] / s.iloc[-days - 1] - 1.0)


def make_metrics(prices: pd.DataFrame, tickers: list[str], benchmark_returns: dict[str, float]) -> pd.DataFrame:
    rows = []
    for ticker in dict.fromkeys(tickers):
        if ticker not in prices.columns:
            continue
        s = prices[ticker].dropna()
        if len(s) < 65:
            continue
        row = {"Ticker": ticker, "Last Close": float(s.iloc[-1]), "As Of": s.index[-1].date().isoformat()}
        excess_values = []
        for label, days in TRADING_WINDOWS.items():
            ret = total_return(s, days)
            bench = benchmark_returns.get(label, np.nan)
            row[f"{label} Return %"] = ret * 100 if pd.notna(ret) else np.nan
            row[f"{label} SPY Excess %"] = (ret - bench) * 100 if pd.notna(ret) and pd.notna(bench) else np.nan
            if pd.notna(ret) and pd.notna(bench):
                excess_values.append((label, ret - bench))
        row["RS Score"] = (
            100 * sum(WEIGHTS[k] * (row[f"{k} SPY Excess %"] / 100) for k in WEIGHTS
                      if pd.notna(row.get(f"{k} SPY Excess %", np.nan)))
            if all(pd.notna(row.get(f"{k} SPY Excess %", np.nan)) for k in WEIGHTS) else np.nan
        )
        row["Above 50D"] = bool(len(s) >= 50 and s.iloc[-1] > s.rolling(50).mean().iloc[-1])
        row["Above 200D"] = bool(len(s) >= 200 and s.iloc[-1] > s.rolling(200).mean().iloc[-1])
        ma50 = s.rolling(50).mean()
        ma200 = s.rolling(200).mean()
        row["50D Above 200D"] = bool(len(s) >= 200 and ma50.iloc[-1] > ma200.iloc[-1])
        rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["RS Rank"] = df["RS Score"].rank(ascending=False, method="min").astype("Int64")
    df["Trend Points"] = df[["Above 50D", "Above 200D", "50D Above 200D"]].sum(axis=1)
    df["Signal"] = np.select(
        [
            (df["RS Score"] > 0) & (df["Trend Points"] == 3),
            (df["RS Score"] > 0) & (df["Trend Points"] >= 2),
            (df["RS Score"] > 0),
            (df["RS Score"] <= 0) & (df["Trend Points"] >= 2),
        ],
        ["STRONG RS + UPTREND", "POSITIVE RS / TREND", "OUTPERFORMING, CHECK TREND", "TREND IMPROVING, RS LAGS"],
        default="WEAK RS / TREND",
    )
    return df.sort_values("RS Score", ascending=False, na_position="last")


def add_labels(metrics: pd.DataFrame, label_map: dict[str, tuple[str, str]]) -> pd.DataFrame:
    out = metrics.copy()
    out["Sector"] = out["Ticker"].map(lambda t: label_map.get(t, ("", ""))[0])
    out["Theme"] = out["Ticker"].map(lambda t: label_map.get(t, ("", ""))[1])
    return out


def main() -> None:
    now = datetime.now(timezone.utc).astimezone()
    print(f"\n{APP_NAME} | Run time: {now:%Y-%m-%d %H:%M:%S %Z}")
    print("Relative strength is measured against SPY (S&P 500 ETF).")

    sector_map = {ticker: (sector, "Sector ETF") for sector, ticker in SECTORS.items()}
    theme_map = {ticker: (sector, theme) for theme, sector, ticker in THEMES}
    stock_map = {ticker: (sector, theme) for ticker, sector, theme in STOCKS}
    all_tickers = [BENCHMARK] + list(SECTORS.values()) + [t[2] for t in THEMES] + [t[0] for t in STOCKS]

    prices = download_prices(all_tickers)
    if BENCHMARK not in prices.columns or prices[BENCHMARK].dropna().empty:
        raise RuntimeError("Benchmark SPY data is missing; cannot calculate relative strength.")
    bench = prices[BENCHMARK]
    bench_returns = {label: total_return(bench, days) for label, days in TRADING_WINDOWS.items()}

    sector_df = add_labels(make_metrics(prices, list(SECTORS.values()), bench_returns), sector_map)

    # Build one theme row per named theme. Some themes intentionally share an ETF proxy,
    # so do not deduplicate the theme table by ticker.
    theme_base = make_metrics(prices, [t[2] for t in THEMES], bench_returns)
    theme_rows = []
    if not theme_base.empty:
        theme_lookup = {row["Ticker"]: row.to_dict() for _, row in theme_base.iterrows()}
        for theme_name, sector_name, proxy_ticker in THEMES:
            if proxy_ticker in theme_lookup:
                row = dict(theme_lookup[proxy_ticker])
                row["Sector"] = sector_name
                row["Theme"] = theme_name
                row["Proxy ETF"] = proxy_ticker
                theme_rows.append(row)
    theme_df = pd.DataFrame(theme_rows)
    if not theme_df.empty:
        theme_df = theme_df.sort_values("RS Score", ascending=False, na_position="last")

    stock_df = add_labels(make_metrics(prices, [t[0] for t in STOCKS], bench_returns), stock_map)

    # Add sector ranks and readable sector names.
    sector_names = {ticker: sector for sector, ticker in SECTORS.items()}
    if not sector_df.empty:
        sector_df["Sector"] = sector_df["Ticker"].map(sector_names)
        sector_df["RS Rank"] = sector_df["RS Score"].rank(ascending=False, method="min").astype("Int64")
    if not theme_df.empty:
        theme_df["RS Rank"] = theme_df["RS Score"].rank(ascending=False, method="min").astype("Int64")

    stamp = now.strftime("%Y%m%d_%H%M%S")
    sector_path = OUT_DIR / "sector_rankings.csv"
    theme_path = OUT_DIR / "theme_rankings.csv"
    stock_path = OUT_DIR / "stock_rankings.csv"
    report_path = OUT_DIR / "latest_report.txt"

    sector_df.to_csv(sector_path, index=False)
    theme_df.to_csv(theme_path, index=False)
    stock_df.to_csv(stock_path, index=False)

    def top_table(df: pd.DataFrame, n: int, title: str, name_col: str = "Ticker") -> list[str]:
        lines = [f"\n{title}", "-" * len(title)]
        if df.empty:
            return lines + ["No usable data returned."]
        cols = [c for c in [name_col, "RS Score", "1M SPY Excess %", "3M SPY Excess %",
                             "6M SPY Excess %", "12M SPY Excess %", "Signal"] if c in df.columns]
        display = df.sort_values("RS Score", ascending=False).head(n)[cols].copy()
        for _, r in display.iterrows():
            parts = []
            for c in cols:
                v = r[c]
                if isinstance(v, (float, np.floating)):
                    parts.append(f"{c}={v:.3f}" if c == "RS Score" else f"{c}={v:+.1f}%")
                else:
                    parts.append(f"{c}={v}")
            lines.append(" | ".join(parts))
        return lines

    report_lines = [
        f"{APP_NAME} — RELATIVE STRENGTH REPORT",
        f"Run time: {now:%Y-%m-%d %H:%M:%S %Z}",
        f"Latest price date: {prices.index[-1].date().isoformat()}",
        f"Benchmark: SPY (S&P 500 ETF)",
        "",
        "Method: weighted excess returns vs SPY: 1M 20%, 3M 30%, 6M 30%, 12M 20%.",
        "Trend checks: price above 50-day average, price above 200-day average, and 50-day average above 200-day average.",
        "Higher RS Score means stronger weighted outperformance versus SPY. Scores are decimal return differences, not percentages.",
        "Data is sourced from Yahoo Finance via yfinance; data can be delayed, incomplete, or corrected.",
    ]
    report_lines += top_table(sector_df, 11, "SECTOR RANKING", "Sector")
    report_lines += top_table(theme_df, 15, "TOP THEMES", "Theme")
    report_lines += top_table(stock_df, 25, "TOP STOCKS", "Ticker")
    report_lines += [
        "",
        "Files saved:",
        f"  {sector_path}",
        f"  {theme_path}",
        f"  {stock_path}",
        "",
        "Disclaimer: For research and education only; not financial advice. Verify data and do your own research.",
    ]
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print("\n".join(report_lines))
    print(f"\nCSV rankings and report saved in: {OUT_DIR}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        sys.exit(130)
    except Exception as exc:
        print(f"\nScanner failed: {exc}", file=sys.stderr)
        print("Check your internet connection, Yahoo Finance availability, and package versions.", file=sys.stderr)
        sys.exit(1)
