import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# --- Page Configuration for Mobile ---
st.set_page_config(page_title="NSE OI Monitor", layout="wide", initial_sidebar_state="collapsed")

# --- Custom CSS for Mobile Friendliness ---
st.markdown("""
    <style>
    .main > div {padding-top: 2rem;}
    div[data-testid="stMetricValue"] {font-size: 1.5rem;}
    .stDataFrame {font-size: 0.8rem;}
    </style>
    """, unsafe_allow_html=True)

# --- Header ---
st.title("📊 NSE Option Chain OI")
st.caption("Live Open Interest Data (Mobile View)")

# --- Sidebar / Info ---
with st.expander("ℹ️ How to use"):
    st.write("1. Enter Symbol (e.g., NIFTY, BANKNIFTY)")
    st.write("2. Click Fetch")
    st.write("3. View Top OI Strikes")
    st.warning("⚠️ NSE may block requests if clicked too frequently. Wait 1 min between refreshes.")

# --- Data Fetching Logic ---
@st.cache_data(ttl=60)  # Cache data for 60 seconds to avoid banning
def get_option_chain(symbol):
    try:
        symbol = symbol.upper()
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        # Initial request to set cookies
        session.get("https://www.nseindia.com", headers=headers)
        
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None, "NSE Blocked Request (Try again later)"
        
        data = response.json()
        records = data['records']['data']
        underlying = data['records']['underlyingValue']
        
        df = pd.DataFrame(records)
        df = df[df['strikePrice'].notna()] # Remove empty rows
        
        # Flatten CE and PE data
        ce = pd.json_normalize(df['CE'])
        pe = pd.json_normalize(df['PE'])
        
        final = pd.concat([df[['strikePrice']], ce.add_prefix('CE_'), pe.add_prefix('PE_')], axis=1)
        
        # Calculate PCR
        final['PCR'] = (final['PE_openInterest'] / final['CE_openInterest']).round(2)
        
        return final, underlying
    except Exception as e:
        return None, str(e)

# --- User Input ---
col1, col2 = st.columns([3, 1])
with col1:
    symbol = st.text_input("Symbol", value="NIFTY").upper()
with col2:
    refresh = st.form_submit_button("🔄 Fetch")

# --- Main Logic ---
if refresh or 'data' not in st.session_state:
    if symbol:
        with st.spinner('Fetching data from NSE...'):
            df, status = get_option_chain(symbol)
            
            if df is not None:
                st.session_state['data'] = df
                st.session_state['underlying'] = status
                st.session_state['time'] = datetime.now().strftime("%H:%M:%S")
            else:
                st.error(f"❌ {status}")
                st.stop()

# --- Display Results ---
if 'data' in st.session_state:
    df = st.session_state['data']
    underlying = st.session_state['underlying']
    time_str = st.session_state['time']
    
    # Top Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Underlying", underlying)
    m2.metric("Last Update", time_str)
    m3.metric("Symbol", symbol)
    
    st.divider()
    
    # Tabs for CE and PE
    tab1, tab2 = st.tabs(["🔴 Max Pain / CE OI", "🟢 PE OI / Support"])
    
    with tab1:
        st.subheader("Top Call Writers (Resistance)")
        # Sort by CE OI
        ce_top = df.nlargest(10, 'CE_openInterest')[['strikePrice', 'CE_openInterest', 'CE_changeinOI', 'PCR']]
        ce_top.columns = ["Strike", "Call OI", "Call Chg", "PCR"]
        st.dataframe(ce_top, use_container_width=True, hide_index=True)
        
    with tab2:
        st.subheader("Top Put Writers (Support)")
        # Sort by PE OI
        pe_top = df.nlargest(10, 'PE_openInterest')[['strikePrice', 'PE_openInterest', 'PE_changeinOI', 'PCR']]
        pe_top.columns = ["Strike", "Put OI", "Put Chg", "PCR"]
        st.dataframe(pe_top, use_container_width=True, hide_index=True)

    # Full Data Download
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Full CSV", csv, "oi_data.csv", "text/csv")