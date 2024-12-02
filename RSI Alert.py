import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import streamlit as st
import numpy as np

# Initialize connection to MetaTrader 5
if not mt5.initialize():
    print("Failed to initialize MT5")
    mt5.shutdown()
    exit()

# Streamlit page configuration
st.set_page_config(page_title="Enhanced USDCAD Analysis", layout='wide')

# Sidebar - Date Range Selector and Alerts
st.sidebar.title("Settings")
start_date = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=30))
end_date = st.sidebar.date_input("End Date", datetime.now())
alert_rsi_level = st.sidebar.slider("RSI Alert Level", 0, 100, (30, 70))

# Fetch Data based on selected date range
symbol = "USDCAD"
timeframe = mt5.TIMEFRAME_H1
utc_from = datetime.combine(start_date, datetime.min.time())
utc_to = datetime.combine(end_date, datetime.min.time())
rates = mt5.copy_rates_range(symbol, timeframe, utc_from, utc_to)
mt5.shutdown()

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

# Calculate RSI
window_length = 14
delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=window_length).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=window_length).mean()
rs = gain / loss
df['RSI'] = 100 - (100 / (1 + rs))

# Calculate Moving Averages and VWAP
df['SMA20'] = df['close'].rolling(window=20).mean()
df['SMA50'] = df['close'].rolling(window=50).mean()
df['VWAP'] = (df['close'] * df['tick_volume']).cumsum() / df['tick_volume'].cumsum()

# Calculate Fibonacci Levels based on last 7 days
last_7_days_data = df[df['time'] >= datetime.now() - timedelta(days=7)]
fib_high = last_7_days_data['high'].max()
fib_low = last_7_days_data['low'].min()
fibonacci_levels = [fib_high - (fib_high - fib_low) * ratio for ratio in [0.236, 0.382, 0.5, 0.618, 0.786]]

# Create Candlestick Chart with Moving Averages and VWAP
fig_candlestick = go.Figure(data=[go.Candlestick(
    x=df['time'], open=df['open'], high=df['high'], low=df['low'], close=df['close'],
    increasing_line_color='cyan', decreasing_line_color='magenta'
)])
fig_candlestick.add_trace(go.Scatter(x=df['time'], y=df['SMA20'], mode='lines', name='SMA20', line=dict(color='blue')))
fig_candlestick.add_trace(go.Scatter(x=df['time'], y=df['SMA50'], mode='lines', name='SMA50', line=dict(color='purple')))
fig_candlestick.add_trace(go.Scatter(x=df['time'], y=df['VWAP'], mode='lines', name='VWAP', line=dict(color='orange')))
fig_candlestick.update_layout(title="Candlestick Chart with Moving Averages & VWAP", template="plotly_dark")

# Create RSI Plot with Alerts
fig_rsi = go.Figure()
fig_rsi.add_trace(go.Scatter(x=df['time'], y=df['RSI'], mode='lines', name='RSI'))
fig_rsi.add_hline(y=alert_rsi_level[0], line=dict(color='green', dash='dash'), annotation_text="RSI Lower Alert", annotation_position="bottom right")
fig_rsi.add_hline(y=alert_rsi_level[1], line=dict(color='red', dash='dash'), annotation_text="RSI Upper Alert", annotation_position="top right")
fig_rsi.update_layout(title="RSI Indicator (14-period)", xaxis_title="Time", yaxis_title="RSI", template="plotly_dark")

# Alert Notification for RSI Breach
rsi_breach = df[(df['RSI'] < alert_rsi_level[0]) | (df['RSI'] > alert_rsi_level[1])]
if not rsi_breach.empty:
    st.sidebar.warning(f"RSI Alert: Level breached at {rsi_breach['time'].iloc[-1]} with RSI {rsi_breach['RSI'].iloc[-1]:.2f}")

# Create Fibonacci Retracement Chart
fig_fib = go.Figure()
fig_fib.add_trace(go.Candlestick(
    x=last_7_days_data['time'], open=last_7_days_data['open'], high=last_7_days_data['high'],
    low=last_7_days_data['low'], close=last_7_days_data['close'],
    increasing_line_color='cyan', decreasing_line_color='magenta', name="7-Day Data"
))
# Add Fibonacci levels
for i, level in enumerate(fibonacci_levels, start=1):
    fig_fib.add_hline(y=level, line=dict(color='purple', dash='dot'), annotation_text=f"Fib Level {i}", annotation_position="top right")
fig_fib.update_layout(title="Fibonacci Retracement Levels (Last 7 Days)", xaxis_title="Time", yaxis_title="Price", template="plotly_dark")

# Create Volume Chart
fig_volume = go.Figure(data=[go.Bar(x=df['time'], y=df['tick_volume'], name='Volume')])
fig_volume.update_layout(title="Trading Volume", xaxis_title="Time", yaxis_title="Volume", template="plotly_dark")

# Display charts in Streamlit
st.plotly_chart(fig_candlestick, use_container_width=True)
st.plotly_chart(fig_rsi, use_container_width=True)
st.plotly_chart(fig_fib, use_container_width=True)
st.plotly_chart(fig_volume, use_container_width=True)
