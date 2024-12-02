import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime

# Initialize MetaTrader5
if not mt5.initialize():
    st.error("Failed to initialize MT5")
    mt5.shutdown()

# Set the Forex pairs to analyze
forex_pairs = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"]

# Fetch historical data for each Forex pair
def get_mt5_data(pair, period=300):
    rates = mt5.copy_rates_from(pair, mt5.TIMEFRAME_H1, datetime.now(), period)
    data = pd.DataFrame(rates)
    data['time'] = pd.to_datetime(data['time'], unit='s')
    data.set_index('time', inplace=True)
    return data

# RSI Calculation
def calculate_rsi(data, period=14):
    delta = data['close'].diff(1)
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# Moving Average Calculation
def calculate_ma(data, short_window=20, long_window=50):
    data['MA_short'] = data['close'].rolling(window=short_window).mean()
    data['MA_long'] = data['close'].rolling(window=long_window).mean()
    return data

# Strategy 1: Low Volatility Trend Buy
def low_volatility_trend(data, volatility_threshold=0.0005, tp=500, sl=300):
    data['volatility'] = data['close'].rolling(window=20).std()
    data['signal'] = np.where(data['volatility'] < volatility_threshold, 'BUY', 'HOLD')
    data['tp'] = tp
    data['sl'] = sl
    return data

# Strategy 2: RSI Buy/Sell based on levels
def rsi_strategy(data, rsi_buy=30, rsi_sell=70, tp=1000, sl=300):
    data['rsi'] = calculate_rsi(data)
    data['signal'] = np.where(data['rsi'] < rsi_buy, 'BUY',
                      np.where(data['rsi'] > rsi_sell, 'SELL', 'HOLD'))
    data['tp'] = tp
    data['sl'] = sl
    return data

# Strategy 3: Moving Average Crossover
def ma_crossover_strategy(data, tp=1000, sl=300):
    data = calculate_ma(data)
    data['signal'] = np.where(data['MA_short'] > data['MA_long'], 'BUY',
                      np.where(data['MA_short'] < data['MA_long'], 'SELL', 'HOLD'))
    data['tp'] = tp
    data['sl'] = sl
    return data

# Run each strategy and display signals
def apply_strategies(pair):
    data = get_mt5_data(pair)

    # Apply Low Volatility Trend
    trend_data = low_volatility_trend(data.copy())
    st.subheader(f"Low Volatility Trend Signals for {pair}")
    st.write(trend_data[['signal', 'tp', 'sl']].tail())

    # Apply RSI Strategy
    rsi_data = rsi_strategy(data.copy())
    st.subheader(f"RSI Strategy Signals for {pair}")
    st.write(rsi_data[['signal', 'tp', 'sl']].tail())

    # Apply MA Crossover Strategy
    ma_data = ma_crossover_strategy(data.copy())
    st.subheader(f"MA Crossover Signals for {pair}")
    st.write(ma_data[['signal', 'tp', 'sl']].tail())

# Streamlit app layout
st.title("Forex Trading Strategies")
selected_pair = st.selectbox("Select Forex Pair", forex_pairs)

# Display strategy results for selected pair
if selected_pair:
    apply_strategies(selected_pair)
