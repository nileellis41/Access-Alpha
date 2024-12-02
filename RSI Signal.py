import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

# Initialize MetaTrader5
if not mt5.initialize():
    print("Failed to initialize MT5")
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
    data['RSI'] = rsi
    return data

# Moving Averages Calculation
def calculate_moving_averages(data, short_period=20, long_period=50):
    data['Short_MA'] = data['close'].rolling(window=short_period).mean()
    data['Long_MA'] = data['close'].rolling(window=long_period).mean()
    return data

# Volatility Score Calculation
def calculate_volatility(data, period=14):
    data['ATR'] = data['high'] - data['low']
    data['Volatility_Score'] = data['ATR'].rolling(window=period).mean()
    return data

# Signal Generation with Strength Highlighting
def generate_signals(data):
    data = calculate_rsi(data)
    data = calculate_moving_averages(data)
    data = calculate_volatility(data)
    
    data['Signal'] = 'Hold'  # Default to Hold
    data['Signal_Strength'] = 'None'  # Default to no strong signal
    
    # Define basic signals
    data.loc[(data['RSI'] < 30) & (data['Short_MA'] > data['Long_MA']), 'Signal'] = 'Buy'  # Buy
    data.loc[(data['RSI'] > 70) & (data['Short_MA'] < data['Long_MA']), 'Signal'] = 'Sell'  # Sell
    
    # Define strong signals
    data.loc[(data['RSI'] < 20) & (data['Short_MA'] > data['Long_MA']), 'Signal_Strength'] = 'Strong Buy'
    data.loc[(data['RSI'] > 80) & (data['Short_MA'] < data['Long_MA']), 'Signal_Strength'] = 'Strong Sell'
    
    return data

# Display Forex Dashboard in Streamlit with Plotly Candlestick, RSI Graph, and Signal Display
def display_forex_dashboard(data, pair_name, filter_signal):
    # Check if the latest signal matches the selected filter
    latest_signal = data['Signal'].iloc[-1]
    if filter_signal != 'All' and latest_signal != filter_signal:
        return  # Skip this pair if it doesn't match the filter

    st.header(f"{pair_name} Forex Analysis")
    
    # Display main indicators and signals
    latest_close = data['close'].iloc[-1]
    latest_rsi = data['RSI'].iloc[-1]
    latest_volatility = data['Volatility_Score'].iloc[-1]
    signal_strength = data['Signal_Strength'].iloc[-1]
    
    # Display signal summary
    st.subheader("Signal Summary")
    st.write(f"**Latest Close**: {latest_close}")
    st.write(f"**RSI**: {latest_rsi:.2f}")
    st.write(f"**Volatility Score**: {latest_volatility:.2f}")
    st.write(f"**Signal**: {latest_signal}")
    
    # Highlight strong signals
    if signal_strength == 'Strong Buy':
        st.markdown("### 🔥 **Strong Buy Signal!**")
    elif signal_strength == 'Strong Sell':
        st.markdown("### 🚨 **Strong Sell Signal!**")
    
    # Plotly Candlestick Chart
    fig = go.Figure(data=[go.Candlestick(
        x=data.index,
        open=data['open'],
        high=data['high'],
        low=data['low'],
        close=data['close'],
        name="Candlestick"
    )])
    
    # Add moving averages to the candlestick chart
    fig.add_trace(go.Scatter(x=data.index, y=data['Short_MA'], mode='lines', name='Short MA'))
    fig.add_trace(go.Scatter(x=data.index, y=data['Long_MA'], mode='lines', name='Long MA'))

    # Annotate the chart with the latest signal
    if latest_signal == 'Buy':
        fig.add_annotation(
            x=data.index[-1],
            y=data['close'].iloc[-1],
            text="Buy Signal",
            showarrow=True,
            arrowhead=1,
            ax=-40,
            ay=-40,
            bgcolor="green",
            font=dict(color="white")
        )
    elif latest_signal == 'Sell':
        fig.add_annotation(
            x=data.index[-1],
            y=data['close'].iloc[-1],
            text="Sell Signal",
            showarrow=True,
            arrowhead=1,
            ax=-40,
            ay=-40,
            bgcolor="red",
            font=dict(color="white")
        )
    
    # Display the Plotly candlestick chart in Streamlit
    st.plotly_chart(fig)

    # Plot RSI Chart using Plotly
    rsi_fig = px.line(data, x=data.index, y="RSI", title="RSI")
    rsi_fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought (70)")
    rsi_fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold (30)")
    st.plotly_chart(rsi_fig)

# Streamlit App Setup
st.title("Forex Trading App - RSI, Moving Averages, and Volatility Analysis with Signal Filter")

# Signal filter selection
filter_signal = st.selectbox("Choose Signal Type to Display:", options=["All", "Buy", "Sell", "Hold"])

# Process each Forex pair
for pair in forex_pairs:
    data = get_mt5_data(pair)
    data = generate_signals(data)
    display_forex_dashboard(data, pair, filter_signal)

# Shut down MetaTrader5 connection
mt5.shutdown()