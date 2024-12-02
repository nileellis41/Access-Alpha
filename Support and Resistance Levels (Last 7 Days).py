import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import streamlit as st

# Initialize connection to MetaTrader 5
if not mt5.initialize():
    print("Failed to initialize MT5")
    mt5.shutdown()
    exit()

# Streamlit page configuration
st.set_page_config(page_title="USDCAD Analysis with RSI and Levels", layout='wide')

# Set up date range selection
st.sidebar.title("Date Range Selector")
start_date = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=30))
end_date = st.sidebar.date_input("End Date", datetime.now())

# Fetch the data based on selected date range
symbol = "USDCAD"
timeframe = mt5.TIMEFRAME_H1  # 1-hour time frame

# Ensure valid date selection
if start_date >= end_date:
    st.error("Error: End date must fall after start date.")
    mt5.shutdown()
else:
    # Retrieve the rates within selected range
    utc_from = datetime.combine(start_date, datetime.min.time())
    utc_to = datetime.combine(end_date, datetime.min.time())

    rates = mt5.copy_rates_range(symbol, timeframe, utc_from, utc_to)

    # Shutdown connection to MT5
    mt5.shutdown()

    # Create a DataFrame from the retrieved data
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')

    # Calculate RSI
    window_length = 14
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window_length).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window_length).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # Get the latest RSI signal
    latest_rsi = df['RSI'].iloc[-1]

    # Calculate support and resistance levels (high and low over the last 7 days)
    last_7_days_data = df[df['time'] >= datetime.now() - timedelta(days=7)]
    resistance_level = last_7_days_data['high'].max()
    support_level = last_7_days_data['low'].min()

    # Create the candlestick chart with RSI signal and support/resistance levels
    fig = go.Figure(data=[go.Candlestick(
        x=df['time'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        increasing_line_color='cyan',
        decreasing_line_color='magenta'
    )])

    # Add markers for support and resistance levels
    fig.add_hline(y=support_level, line=dict(color='green', dash='dash'), annotation_text="Support", annotation_position="top left")
    fig.add_hline(y=resistance_level, line=dict(color='red', dash='dash'), annotation_text="Resistance", annotation_position="top right")

    # Add a marker for the latest RSI signal on the candlestick chart
    fig.add_trace(go.Scatter(
        x=[df['time'].iloc[-1]],
        y=[df['close'].iloc[-1]],
        mode='markers+text',
        marker=dict(size=10, color='yellow'),
        text=f"RSI: {latest_rsi:.2f}",
        textposition="bottom right",
        name="Latest RSI"
    ))

    # Update layout for dark theme
    fig.update_layout(
        title=f'{symbol} Candlestick Chart with RSI and Support/Resistance Levels',
        xaxis_title='Time',
        yaxis_title='Price',
        template='plotly_dark',
        xaxis_rangeslider_visible=False
    )

    # Create RSI plot
    fig_rsi = go.Figure()
    fig_rsi.add_trace(go.Scatter(
        x=df['time'], y=df['RSI'], mode='lines', name='RSI'
    ))

    # Add a marker for the latest RSI signal on the RSI plot
    fig_rsi.add_trace(go.Scatter(
        x=[df['time'].iloc[-1]],
        y=[latest_rsi],
        mode='markers+text',
        marker=dict(size=10, color='yellow'),
        text=f"{latest_rsi:.2f}",
        textposition="top right",
        name="Latest RSI"
    ))

    # Add overbought/oversold thresholds
    fig_rsi.add_hline(y=70, line=dict(color='red', dash='dash'), annotation_text="Overbought", annotation_position="top left")
    fig_rsi.add_hline(y=30, line=dict(color='green', dash='dash'), annotation_text="Oversold", annotation_position="bottom left")

    # Update layout for dark theme
    fig_rsi.update_layout(
        title='RSI Indicator (14-period)',
        xaxis_title='Time',
        yaxis_title='RSI',
        template='plotly_dark',
    )

    # Display the charts in Streamlit
    st.plotly_chart(fig, use_container_width=True)
    st.plotly_chart(fig_rsi, use_container_width=True)

    # Display support and resistance levels
    st.sidebar.subheader("Support and Resistance Levels (Last 7 Days)")
    st.sidebar.write(f"Resistance Level: {resistance_level}")
    st.sidebar.write(f"Support Level: {support_level}")
