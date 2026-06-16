import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

st.set_page_config(page_title="NSE OI Monitor", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    .main > div {padding-top: 2rem;}
    div[data-testid="stMetricValue"] {font-size: 1.6rem;}
    .stDataFrame {font-size: 0.85rem;}
    </style>
    """, unsafe_allow_html=True)

st.title("📊 NSE Option Chain OI")
st.caption("Live Open Interest Data (Mobile View)")

with st.expander("ℹ️ How to use & Important Note"):
    st.write("1. Enter Symbol (NIFTY / BANKNIFTY / FINNIFTY etc)")
    st.write("2. Click 'Fetch Data'")
    st.warning("⚠️ **NSE blocks cloud servers very often.** If you keep getting blocked, try again after 30–60 seconds. If it continues failing, this free scraping method is not very reliable on Streamlit Cloud.")

# Improved Data Fetching
@st.cache_data(ttl=45)
def get_option_chain(symbol):
    try:
        symbol = symbol.upper().strip()
        session = requests.Session()
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.nseindia.com/option-chain",
            "Origin": "https://www.nseindia.com",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Connection": "keep-alive",
            "Sec-Ch-Ua": '"Chromium";v="129", "Not=A?Brand";v="8"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
        }
        
        # Important: Visit multiple pages to set cookies properly
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        time.sleep(0.7)
        session.get("https://www.nseindia.com/option-chain", headers=headers, timeout=10)
        time.sleep(0.8)
        
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        response = session.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return None, f"NSE Blocked (Status {response.status_code}). Try again in 30-60 seconds."
        
        data = response.json()
        records = data.get('records', {}).get('data', [])
        underlying = data.get('records', {}).get('underlyingValue', 'N/A')
        
        if not records:
            return None, "No data received from NSE"
        
        df = pd.DataFrame(records)
        df = df[df['strikePrice'].notna()]
        
        ce = pd.json_normalize(df['CE'])
        pe = pd.json_normalize(df['PE'])
        
        final = pd.concat([
            df[['strikePrice']].reset_index(drop=True), 
            ce.add_prefix('CE_').reset_index(drop=True), 
            pe.add_prefix('PE_').reset_index(drop=True)
        ], axis=1)
        
        final['PCR'] = (final.get('PE_openInterest', 0) / final.get('CE_openInterest', 1)).round(2)
        final = final.sort_values('strikePrice')
        
        return final, underlying
    except Exception as e:
        return None, f"Error: {str(e)}"

# UI
symbol = st.text_input("Symbol", value="NIFTY").strip().upper()

if st.button("🔄 Fetch Data", type="primary", use_container_width=True):
    with st.spinner("Connecting to NSE..."):
        df, status = get_option_chain(symbol)
        
        if df is not None:
            st.session_state['data'] = df
            st.session_state['underlying'] = status
            st.session_state['time'] = datetime.now().strftime("%H:%M:%S")
            st.success(f"✅ Data loaded successfully for {symbol}!")
        else:
            st.error(status)
            st.info("💡 Tip: Wait 30–60 seconds and try again. NSE often temporarily blocks cloud IPs.")

# Display Results
if 'data' in st.session_state:
    df = st.session_state['data']
    underlying = st.session_state.get('underlying', 'N/A')
    time_str = st.session_state.get('time', 'N/A')
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Underlying Value", underlying)
    col2.metric("Last Updated", time_str)
    col3.metric("Symbol", symbol)
    
    st.divider()
    
    tab1, tab2 = st.tabs(["🔴 Call OI (Resistance)", "🟢 Put OI (Support)"])
    
    with tab1:
        st.subheader("Highest Call Open Interest")
        ce_top = df.nlargest(12, 'CE_openInterest')[['strikePrice', 'CE_openInterest', 'CE_changeinOI', 'PCR']]
        ce_top.columns = ["Strike Price", "CE OI", "CE OI Change", "PCR"]
        st.dataframe(ce_top, use_container_width=True, hide_index=True)
        
    with tab2:
        st.subheader("Highest Put Open Interest")
        pe_top = df.nlargest(12, 'PE_openInterest')[['strikePrice', 'PE_openInterest', 'PE_changeinOI', 'PCR']]
        pe_top.columns = ["Strike Price", "PE OI", "PE OI Change", "PCR"]
        st.dataframe(pe_top, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Full Data as CSV", csv, f"{symbol}_oi_data.csv", "text/csv")
