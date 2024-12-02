import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import streamlit as st
import numpy as np
from statsmodels.tsa.arima.model import ARIMA
from fredapi import Fred

# Initialize MT5 connection
mt5.initialize()

# Streamlit page config
st.set_page_config(page_title="Advanced USD/CAD Analysis with Oil Correlation", layout="wide")

# Sidebar - Date Range Selector and FRED API Key
st.sidebar.title("Settings")
start_date = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=30))
end_date = st.sidebar.date_input("End Date", datetime.now())
fred_api_key = st.sidebar.text_input("FRED API Key", type="password")

# Fetch data for main symbol (USD/CAD)
symbol = "USDCAD"
timeframe = mt5.TIMEFRAME_H1
utc_from = datetime.combine(start_date, datetime.min.time())
utc_to = datetime.combine(end_date, datetime.min.time())
rates = mt5.copy_rates_range(symbol, timeframe, utc_from, utc_to)

# Check if data retrieval was successful
if rates is None or len(rates) == 0:
    st.error("Data retrieval failed. Please check the date range or try again later.")
else:
    # Create DataFrame and add time column as datetime
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')

    # Multi-Timeframe Comparison
    def fetch_data(symbol, timeframe, start_date, end_date):
        utc_from = datetime.combine(start_date, datetime.min.time())
        utc_to = datetime.combine(end_date, datetime.min.time())
        data = mt5.copy_rates_range(symbol, timeframe, utc_from, utc_to)
        if data is not None and len(data) > 0:
            df = pd.DataFrame(data)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        else:
            return pd.DataFrame()  # Return empty DataFrame if no data

    timeframes = {'1H': mt5.TIMEFRAME_H1, '4H': mt5.TIMEFRAME_H4, 'Daily': mt5.TIMEFRAME_D1}
    multiframe_data = {tf: fetch_data(symbol, tf_code, start_date, end_date) for tf, tf_code in timeframes.items()}

    for tf, data in multiframe_data.items():
        if not data.empty:
            fig = go.Figure(data=[go.Candlestick(
                x=data['time'], open=data['open'], high=data['high'], low=data['low'], close=data['close'],
                increasing_line_color='cyan', decreasing_line_color='magenta'
            )])
            fig.update_layout(title=f"{symbol} - {tf} Candlestick Chart", template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write(f"No data available for {tf} timeframe.")

    # Correlation Matrix (USD/CAD, EUR/USD, GBP/USD, Oil)
    related_symbols = ["USDCAD", "EURUSD", "GBPUSD"]
    correlation_data = {}

    for sym in related_symbols:
        symbol_data = mt5.copy_rates_range(sym, mt5.TIMEFRAME_H1, utc_from, utc_to)
        if symbol_data is not None and len(symbol_data) > 0:
            symbol_df = pd.DataFrame(symbol_data)
            if 'close' in symbol_df.columns:
                correlation_data[sym] = symbol_df['close']
            else:
                st.write(f"No 'close' data available for {sym}. Skipping.")
        else:
            st.write(f"No data available for {sym}. Skipping.")

    # Fetch Oil Prices from FRED
    if fred_api_key:
        fred = Fred(api_key=fred_api_key)
        try:
            oil_data = fred.get_series('DCOILWTICO', start_date, end_date)
            oil_df = pd.DataFrame(oil_data, columns=['WTI_Oil'])
            oil_df.index = oil_df.index.tz_localize('UTC')  # Match time zone with MetaTrader 5 data
            oil_df = oil_df.resample('H').ffill()  # Resample to hourly and forward fill missing data
            correlation_data['WTI_Oil'] = oil_df['WTI_Oil']
        except Exception as e:
            st.error(f"Failed to retrieve oil data: {e}")
    else:
        st.warning("Please enter a valid FRED API Key to retrieve oil data.")

    # Calculate and Display Correlation Matrix
    if correlation_data:
        correlation_df = pd.DataFrame(correlation_data).corr()
        st.write("Correlation Matrix with Oil")
        st.write(correlation_df)
    else:
        st.write("Not enough data for correlation matrix.")

# Shutdown MT5 connection at the end
mt5.shutdown()
