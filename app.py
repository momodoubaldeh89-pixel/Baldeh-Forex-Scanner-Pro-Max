from datetime import datetime
import math
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import Baldeh_Forex_scanner as base

st.set_page_config(page_title="Baldeh_Forex Scanner Pro Max", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

# Mobile-first visual system; signal colors remain explicit in both tables and cards.
st.markdown("""
<style>
:root { --bull:#16803c; --bear:#c62828; --mixed:#d9a400; }
.block-container {padding-top:1rem;padding-bottom:2rem;max-width:1500px}
h1 {font-size:clamp(1.55rem,4vw,2.5rem)!important}
h2 {font-size:clamp(1.2rem,3vw,1.8rem)!important}
[data-testid="stMetric"] {background:rgba(128,128,128,.09);padding:.7rem;border-radius:.7rem;border:1px solid rgba(128,128,128,.15)}
.signal-card {padding:.7rem .85rem;border-radius:.65rem;margin:.25rem 0;font-weight:700;color:white;text-align:center}
.bull {background:#16803c}.bear {background:#c62828}.mixed {background:#d9a400;color:#181818}
.small-note {font-size:.85rem;opacity:.82}
[data-testid="stDataFrame"] {width:100%}
</style>
""", unsafe_allow_html=True)

st.title("📊 Baldeh_Forex Scanner Pro Max")
st.caption("Forex + US stocks • Opportunity ranking • Market regime • Signals • Risk planning • Mobile-friendly")

with st.sidebar:
    st.header("Scanner controls")
    max_rows = st.slider("Rows to show per ranking", 5, 50, 20, 5)
    st.caption("Market data supplied by Yahoo Finance via yfinance. Data availability and delays may vary.")

FOREX_PAIRS = {
    "EUR/USD":"EURUSD=X", "GBP/USD":"GBPUSD=X", "USD/JPY":"JPY=X", "USD/CHF":"CHF=X",
    "AUD/USD":"AUDUSD=X", "NZD/USD":"NZDUSD=X", "USD/CAD":"CAD=X", "EUR/GBP":"EURGBP=X",
    "EUR/JPY":"EURJPY=X", "GBP/JPY":"GBPJPY=X", "AUD/JPY":"AUDJPY=X", "EUR/AUD":"EURAUD=X",
    "GBP/CHF":"GBPCHF=X", "USD/CNH":"CNH=X", "USD/SEK":"SEK=X", "USD/NOK":"NOK=X"
}

@st.cache_data(ttl=900, show_spinner=False)
def get_forex_scan():
    tickers=list(FOREX_PAIRS.values())
    raw=yf.download(tickers=tickers, period="1y", interval="1d", auto_adjust=True, group_by="column", threads=True, progress=False)
    if raw is None or raw.empty: return pd.DataFrame(), pd.DataFrame()
    if isinstance(raw.columns,pd.MultiIndex):
        close=raw['Close'].copy() if 'Close' in raw.columns.get_level_values(0) else raw.xs('Close',axis=1,level=-1)
        high=raw['High'].copy() if 'High' in raw.columns.get_level_values(0) else None
        low=raw['Low'].copy() if 'Low' in raw.columns.get_level_values(0) else None
    else:
        close=raw[['Close']].rename(columns={'Close':tickers[0]}); high=raw[['High']].rename(columns={'High':tickers[0]}); low=raw[['Low']].rename(columns={'Low':tickers[0]})
    rows=[]; histories={}
    for pair,ticker in FOREX_PAIRS.items():
        if ticker not in close.columns: continue
        s=close[ticker].dropna()
        if len(s)<55: continue
        histories[pair]=s
        ema20=s.ewm(span=20,adjust=False).mean(); ema50=s.ewm(span=50,adjust=False).mean(); ema200=s.ewm(span=200,adjust=False).mean()
        delta=s.diff(); gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean(); loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
        rs=gain/loss.replace(0,np.nan); rsi=100-(100/(1+rs))
        avgvol=None
        last=float(s.iloc[-1]); rsi_last=float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else 50.0
        above20=last>float(ema20.iloc[-1]); above50=last>float(ema50.iloc[-1]); trendstack=float(ema20.iloc[-1])>float(ema50.iloc[-1])
        momentum=float(s.iloc[-1]/s.iloc[-6]-1)*100 if len(s)>6 else 0
        prior=s.iloc[-21:-1]
        breakout_up=bool(len(prior)>=15 and last>float(prior.max())); breakout_down=bool(len(prior)>=15 and last<float(prior.min()))
        checks=int(above20)+int(above50)+int(trendstack)+int(rsi_last>=50 and rsi_last<=70)
        bearchecks=int(not above20)+int(not above50)+int(not trendstack)+int(rsi_last<50)
        score=round((int(above20)*20+int(above50)*25+int(trendstack)*25+(20 if 50<=rsi_last<=70 else 10 if rsi_last>70 else 0)+(10 if momentum>0 else 0)),1)
        if breakout_up: score=min(100,score+8)
        if breakout_down: score=max(0,score-8)
        if score>=70 and above50 and rsi_last>=50: signal='BULLISH'
        elif score<=35 and not above50 and rsi_last<50: signal='BEARISH'
        else: signal='MIXED'
        rows.append({'Pair':pair,'Ticker':ticker,'Last':last,'RSI (14)':round(rsi_last,1),'Momentum 5D %':round(momentum,2),'Above EMA20':above20,'Above EMA50':above50,'EMA20 > EMA50':trendstack,'20D Breakout':'UP' if breakout_up else 'DOWN' if breakout_down else '—','Opportunity Score':score,'Signal':signal,'As Of':s.index[-1].date().isoformat()})
    df=pd.DataFrame(rows)
    if not df.empty: df=df.sort_values(['Opportunity Score','Momentum 5D %'],ascending=False).reset_index(drop=True); df.insert(0,'Rank',range(1,len(df)+1))
    return df,histories

@st.cache_data(ttl=900, show_spinner=False)
def get_stock_scan():
    sectors_map={ticker:(sector,'Sector ETF') for sector,ticker in base.SECTORS.items()}
    all_tickers=list(dict.fromkeys([base.BENCHMARK]+list(base.SECTORS.values())+[t[2] for t in base.THEMES]+[t[0] for t in base.STOCKS]))
    prices=base.download_prices(all_tickers)
    if base.BENCHMARK not in prices.columns: raise RuntimeError('SPY benchmark data was not returned by Yahoo Finance.')
    benchmark=prices[base.BENCHMARK]
    benchmark_returns={label:base.total_return(benchmark,days) for label,days in base.TRADING_WINDOWS.items()}
    sector=base.add_labels(base.make_metrics(prices,list(base.SECTORS.values()),benchmark_returns),sectors_map)
    if not sector.empty: sector['Sector']=sector['Ticker'].map({t:s for s,t in base.SECTORS.items()}); sector=sector.sort_values('RS Score',ascending=False)
    theme_base=base.make_metrics(prices,[t[2] for t in base.THEMES],benchmark_returns)
    theme_lookup={row['Ticker']:row.to_dict() for _,row in theme_base.iterrows()} if not theme_base.empty else {}
    theme_rows=[]
    for name,sector_name,ticker in base.THEMES:
        if ticker in theme_lookup:
            row=dict(theme_lookup[ticker]); row['Sector']=sector_name; row['Theme']=name; row['Proxy ETF']=ticker; theme_rows.append(row)
    themes=pd.DataFrame(theme_rows)
    if not themes.empty: themes=themes.sort_values('RS Score',ascending=False)
    stock=base.add_labels(base.make_metrics(prices,[t[0] for t in base.STOCKS],benchmark_returns),{t:(s,theme) for t,s,theme in base.STOCKS})
    if not stock.empty: stock=stock.sort_values('RS Score',ascending=False)
    return sector,themes,stock,prices

@st.cache_data(ttl=900, show_spinner=False)
def get_regime():
    raw=yf.download(tickers=['SPY','QQQ','IWM','^VIX'],period='1y',interval='1d',auto_adjust=True,group_by='column',threads=True,progress=False)
    if raw is None or raw.empty: return pd.DataFrame(), 'UNKNOWN'
    close=raw['Close'] if isinstance(raw.columns,pd.MultiIndex) else raw[['Close']]
    rows=[]
    for ticker,label in [('SPY','Broad US market'),('QQQ','Nasdaq 100'),('IWM','Small caps')]:
        if ticker not in close.columns: continue
        s=close[ticker].dropna()
        if len(s)<50: continue
        e50=s.rolling(50).mean(); e200=s.rolling(200).mean()
        rows.append({'Market':label,'Ticker':ticker,'Last':float(s.iloc[-1]),'Above 50D':bool(s.iloc[-1]>e50.iloc[-1]),'Above 200D':bool(len(s)>=200 and s.iloc[-1]>e200.iloc[-1]),'50D > 200D':bool(len(s)>=200 and e50.iloc[-1]>e200.iloc[-1]),'5D %':float((s.iloc[-1]/s.iloc[-6]-1)*100) if len(s)>6 else np.nan})
    df=pd.DataFrame(rows)
    spy=close['SPY'].dropna() if 'SPY' in close.columns else pd.Series(dtype=float)
    if len(spy)<50: regime='UNKNOWN'
    else:
        e50=spy.rolling(50).mean().iloc[-1]; e200=spy.rolling(200).mean().iloc[-1] if len(spy)>=200 else np.nan
        regime='RISK-ON / BULLISH' if spy.iloc[-1]>e50 and pd.notna(e200) and spy.iloc[-1]>e200 else 'RISK-OFF / BEARISH' if spy.iloc[-1]<e50 and pd.notna(e200) and spy.iloc[-1]<e200 else 'MIXED / TRANSITION'
    return df,regime

def signal_style(val):
    v=str(val).upper()
    if 'BULL' in v or 'STRONG RS' in v or 'POSITIVE RS' in v: return 'background-color:#16803c;color:white;font-weight:700'
    if 'BEAR' in v or 'WEAK RS' in v: return 'background-color:#c62828;color:white;font-weight:700'
    return 'background-color:#f2cf42;color:#222;font-weight:700'

def styled_table(df, height=480):
    if df is None or df.empty: st.info('No rows returned for this scan.'); return
    styler=df.style
    if 'Signal' in df.columns: styler=styler.map(signal_style,subset=['Signal'])
    st.dataframe(styler,use_container_width=True,hide_index=True,height=height)

def signal_card(label,signal,detail=''):
    cls='bull' if 'BULL' in signal.upper() else 'bear' if 'BEAR' in signal.upper() else 'mixed'
    st.markdown(f'<div class="signal-card {cls}">{label}: {signal}<br><span style="font-weight:400;font-size:.85rem">{detail}</span></div>',unsafe_allow_html=True)

# Header and run control
col1,col2=st.columns([1,2])
with col1: refresh=st.button('🔄 Refresh all markets',type='primary',use_container_width=True)
with col2: st.markdown('<p class="small-note">Cached for 15 minutes to reduce repeated downloads. Use Refresh to request fresh data.</p>',unsafe_allow_html=True)
if refresh:
    get_forex_scan.clear(); get_stock_scan.clear(); get_regime.clear()

try:
    with st.spinner('Loading forex, stocks, sectors, themes and market regime…'):
        forex,forex_histories=get_forex_scan(); sectors,themes,stocks,prices=get_stock_scan(); regime_df,regime=get_regime()
except Exception as exc:
    st.error(f'Could not complete one or more market downloads: {exc}')
    st.info('Try Refresh again. Yahoo Finance can occasionally return incomplete or unavailable data.')
    st.stop()

# Opportunity snapshot
b1,b2,b3,b4=st.columns(4)
b1.metric('Forex pairs scanned',len(forex))
b2.metric('Stocks ranked',len(stocks))
b3.metric('Sector ETFs',len(sectors))
b4.metric('Market regime',regime)
signal_card('US MARKET REGIME',regime,'SPY price versus 50-day and 200-day moving averages')

# Unified opportunity feed
feed=[]
if not forex.empty:
    for _,r in forex.iterrows(): feed.append({'Asset Class':'Forex','Opportunity':r['Pair'],'Score':r['Opportunity Score'],'Signal':r['Signal'],'Momentum %':r['Momentum 5D %'],'Details':f"RSI {r['RSI (14)']} • {r['20D Breakout']} breakout"})
if not stocks.empty:
    for _,r in stocks.head(100).iterrows():
        sig='BULLISH' if r['Signal'] in ['STRONG RS + UPTREND','POSITIVE RS / TREND'] else 'BEARISH' if r['Signal']=='WEAK RS / TREND' else 'MIXED'
        feed.append({'Asset Class':'US Stock','Opportunity':r['Ticker'],'Score':round(float(r['RS Score'])*100,1) if pd.notna(r['RS Score']) else np.nan,'Signal':sig,'Momentum %':r.get('3M Return %',np.nan),'Details':f"{r.get('Sector','')} • {r['Signal']}"})
feed_df=pd.DataFrame(feed)
if not feed_df.empty: feed_df=feed_df.sort_values('Score',ascending=False,na_position='last').reset_index(drop=True); feed_df.insert(0,'Rank',range(1,len(feed_df)+1))

tabs=st.tabs(['🚀 Opportunities','💱 Forex Scanner','📈 Stocks','🏭 Sectors & Themes','🌦️ Market Regime','🔔 Alerts','🧮 Risk Calculator','📘 Guide & Downloads'])
with tabs[0]:
    st.subheader('Smart Opportunity Ranking Engine')
    st.write('Combines forex technical momentum and stock relative strength into a single watchlist. Scores are screening indicators, not probabilities.')
    if not feed_df.empty:
        cls=st.selectbox('Asset class',['All','Forex','US Stock'],key='feed_class')
        sigf=st.selectbox('Signal filter',['All','BULLISH','BEARISH','MIXED'],key='feed_signal')
        f=feed_df.copy()
        if cls!='All': f=f[f['Asset Class']==cls]
        if sigf!='All': f=f[f['Signal']==sigf]
        styled_table(f.head(max_rows),500)
        st.download_button('Download opportunity feed CSV',f.to_csv(index=False).encode(), 'baldeh_opportunity_feed.csv','text/csv',use_container_width=True)
    else: st.warning('No combined opportunity rows are currently available.')
with tabs[1]:
    st.subheader('Forex Scanner — trend, RSI, momentum and breakout')
    st.caption('Daily candles are used in this release. Yahoo Finance availability for intraday FX data can vary; the 4-hour control is reserved for a future verified intraday feed.')
    if not forex.empty:
        sig=st.selectbox('Forex signal filter',['All','BULLISH','BEARISH','MIXED'],key='fx_filter')
        f=forex if sig=='All' else forex[forex['Signal']==sig]
        styled_table(f.head(max_rows),520)
        chosen=st.selectbox('Inspect pair',forex['Pair'].tolist())
        s=forex_histories.get(chosen)
        if s is not None:
            st.line_chart(s.tail(120),use_container_width=True)
            last=forex[forex['Pair']==chosen].iloc[0]; signal_card(chosen,last['Signal'],f"Score {last['Opportunity Score']}/100 • RSI {last['RSI (14)']} • 5D momentum {last['Momentum 5D %']}%")
        st.download_button('Download forex scan CSV',forex.to_csv(index=False).encode(),'baldeh_forex_signals.csv','text/csv',use_container_width=True)
    else: st.warning('No forex pairs returned data. Yahoo Finance may not provide every requested pair.')
with tabs[2]:
    st.subheader('Individual stock relative strength')
    if not stocks.empty:
        x,y=st.columns(2)
        with x: sector_filter=st.selectbox('Sector filter',['All sectors']+sorted(stocks['Sector'].dropna().unique().tolist()),key='stock_sector')
        with y: query=st.text_input('Search ticker / sector / theme',placeholder='e.g. NVDA, semiconductors')
        f=stocks.copy()
        if sector_filter!='All sectors': f=f[f['Sector']==sector_filter]
        if query:
            mask=False
            for c in ['Ticker','Sector','Theme']:
                if c in f: mask=mask|f[c].astype(str).str.contains(query,case=False,na=False)
            f=f[mask]
        styled_table(f.head(max_rows),520)
        st.download_button('Download stock rankings CSV',stocks.to_csv(index=False).encode(),'baldeh_stock_rankings.csv','text/csv',use_container_width=True)
    else: st.warning('No stock rows were returned.')
with tabs[3]:
    st.subheader('Sector and investment theme leadership')
    st.markdown('**Sector ETFs**'); styled_table(sectors.head(max_rows),400)
    st.markdown('**Themes**')
    if not themes.empty:
        sf=st.selectbox('Theme sector filter',['All sectors']+sorted(themes['Sector'].dropna().unique().tolist()))
        f=themes if sf=='All sectors' else themes[themes['Sector']==sf]
        styled_table(f.head(max_rows),450)
    st.download_button('Download sector rankings CSV',sectors.to_csv(index=False).encode(),'baldeh_sector_rankings.csv','text/csv',use_container_width=True)
    st.download_button('Download theme rankings CSV',themes.to_csv(index=False).encode(),'baldeh_theme_rankings.csv','text/csv',use_container_width=True)
with tabs[4]:
    st.subheader('Market Regime Detector')
    signal_card('CURRENT REGIME',regime,'Based on SPY versus its 50D and 200D averages')
    if not regime_df.empty: styled_table(regime_df,300)
    st.markdown('**Interpretation**')
    st.write('- **RISK-ON / BULLISH:** SPY is above its 50-day and 200-day moving averages.\n- **RISK-OFF / BEARISH:** SPY is below both averages.\n- **MIXED / TRANSITION:** signals disagree or long-term data is insufficient.')
with tabs[5]:
    st.subheader('In-app Opportunity Alerts')
    st.write('This creates an alert list each time the scan runs. It does not send push, email, or SMS notifications in this version.')
    if not forex.empty:
        alert_score=st.slider('Minimum forex opportunity score',0,100,70,5)
        fxalerts=forex[(forex['Opportunity Score']>=alert_score)&(forex['Signal']=='BULLISH')].copy()
        st.markdown('**Bullish forex candidates**'); styled_table(fxalerts,350)
    else: fxalerts=pd.DataFrame()
    if not stocks.empty:
        rs_alert=st.slider('Minimum stock RS score (vs SPY)',-0.10,0.10,0.02,0.01)
        stalerts=stocks[(stocks['RS Score']>=rs_alert)&(stocks['Signal'].isin(['STRONG RS + UPTREND','POSITIVE RS / TREND']))].copy()
        st.markdown('**Positive relative-strength stock candidates**'); styled_table(stalerts.head(max_rows),400)
    else: stalerts=pd.DataFrame()
    alert_parts=[]
    if not fxalerts.empty: alert_parts.append(fxalerts.assign(**{'Asset Class':'Forex'}))
    if not stalerts.empty: alert_parts.append(stalerts.assign(**{'Asset Class':'US Stock'}))
    if alert_parts:
        alert_df=pd.concat(alert_parts,ignore_index=True,sort=False)
        st.download_button('Download current alert list',alert_df.to_csv(index=False).encode(),'baldeh_alerts.csv','text/csv',use_container_width=True)
    else: st.info('No candidates currently match your alert thresholds.')
with tabs[6]:
    st.subheader('Position Risk Calculator')
    st.write('Calculate position sizing from account risk and stop distance. This generic calculator does not place trades; pip value and contract size differ by broker and pair.')
    a,b=st.columns(2)
    with a:
        account=st.number_input('Account balance',min_value=0.0,value=1000.0,step=100.0)
        risk_pct=st.number_input('Risk per trade (%)',min_value=0.1,max_value=5.0,value=1.0,step=0.1)
        entry=st.number_input('Entry price',min_value=0.00001,value=1.10000,step=0.001,format='%.5f')
    with b:
        stop=st.number_input('Stop-loss price',min_value=0.00001,value=1.09500,step=0.001,format='%.5f')
        pip_size=st.selectbox('Pip size',['0.0001 (most non-JPY FX pairs)','0.01 (JPY-style quotes)','Custom'],index=0)
        custom_pip=st.number_input('Custom pip size',min_value=0.000001,value=0.0001,format='%.6f') if pip_size=='Custom' else None
    pip=custom_pip if pip_size=='Custom' else (0.01 if pip_size.startswith('0.01') else 0.0001)
    risk_cash=account*risk_pct/100
    stop_pips=abs(entry-stop)/pip
    if stop_pips>0:
        st.metric('Cash risk at stop',f'{risk_cash:,.2f} account currency')
        st.metric('Stop distance',f'{stop_pips:,.1f} pips')
        st.metric('Risk budget per pip',f'{risk_cash/stop_pips:,.4f} account currency / pip')
        st.caption('To estimate lot size, divide risk budget per pip by your broker-specific pip value per standard lot. Confirm pip value and account currency with your broker.')
    else: st.warning('Entry and stop-loss must be different.')
with tabs[7]:
    st.subheader('How the scanner works')
    st.markdown("""
    **Signal colors used throughout the app**
    - 🟢 **Green — Bullish:** trend and momentum conditions align positively.
    - 🔴 **Red — Bearish:** trend and momentum conditions align negatively.
    - 🟡 **Yellow — Mixed:** conditions conflict, are weak, or need confirmation.

    **Forex score:** EMA20/EMA50 trend checks, RSI(14), recent momentum, and a 20-session high/low breakout. The score is a heuristic ranking, not a probability of success.

    **US stock score:** the original weighted relative-strength score compares 1M (20%), 3M (30%), 6M (30%), and 12M (20%) excess returns against SPY. Trend checks use 50-day and 200-day moving averages.

    **Alerts:** currently displayed in the app and downloadable as CSV; background notifications require a separate notification service and credentials.

    **Limitations:** market data can be delayed, incomplete, or revised. Forex data and trading hours may differ from broker feeds. This educational research tool does not execute trades and is not financial advice. Validate signals and use your own risk controls.
    """)
    st.download_button('Download combined opportunity feed CSV',feed_df.to_csv(index=False).encode() if not feed_df.empty else b'', 'baldeh_opportunity_feed.csv','text/csv',use_container_width=True)

st.caption(f"Baldeh_Forex Scanner Pro Max • Data refresh session: {datetime.now().astimezone():%Y-%m-%d %H:%M %Z} • No trade execution")
