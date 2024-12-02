import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime

account_number=5031393910
password="A!VxNeC4"
server="MetaQuotes-Demo"

# Initialize MT5 connection
def initialize_mt5(account_number, password, server):
    mt5.initialize()
    mt5.login(account_number, password=password, server=server)

# Fetch historical data for USD/CAD
def get_usdcad_data():
    rates = mt5.copy_rates_from_pos("USDCAD", mt5.TIMEFRAME_H1, 0, 500)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

# Calculate RSI
def calculate_rsi(data, period=14):
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# Place a trade
def place_trade(symbol, action, lot_size):
    price = mt5.symbol_info_tick(symbol).ask if action == "buy" else mt5.symbol_info_tick(symbol).bid
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": mt5.ORDER_TYPE_BUY if action == "buy" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "deviation": 10,
        "magic": 234000,
        "comment": "USD/CAD strategy",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    return result

# Streamlit Dashboard
st.title("USD/CAD Trading Strategy Dashboard")

# MT5 Login Inputs
account_number = st.text_input("Account Number", type="password")
password = st.text_input("Password", type="password")
server = st.text_input("Server")

if st.button("Initialize MT5"):
    initialize_mt5(account_number, password, server)
    st.success("MT5 Initialized")

# Strategy Parameters
rsi_threshold = st.slider("RSI Threshold (for Mean Reversion)", 0, 100, 30)
lot_size = st.number_input("Lot Size", min_value=0.01, max_value=10.0, value=0.1)

# Fetch Data and Calculate RSI
df = get_usdcad_data()
df['RSI'] = calculate_rsi(df)

# Display Data and Chart
st.subheader("USD/CAD Historical Data")
st.write(df.tail())
st.line_chart(df.set_index('time')['close'])

# Check RSI Condition and Place Trade
latest_rsi = df['RSI'].iloc[-1]
if latest_rsi < rsi_threshold:
    st.write("RSI is below threshold, indicating a buy signal.")
    if st.button("Execute Buy Trade"):
        trade_result = place_trade("USDCAD", "buy", lot_size)
        st.write("Trade Result:", trade_result)
else:
    st.write("No buy signal - RSI is above threshold.")

# Streamlit will auto-refresh on interaction, making it suitable for live trading environments