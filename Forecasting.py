import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import streamlit as st
import numpy as np
from statsmodels.tsa.arima.model import ARIMA

# Initialize MT5 connection
mt5.initialize()

# Streamlit page config
st.set_page_config(page_title="Advanced USD/CAD Analysis", layout="wide")

# Sidebar - Date Range Selector
st.sidebar.title("Settings")
start_date = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=30))
end_date = st.sidebar.date_input("End Date", datetime.now())

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

    # Placeholder Sentiment Analysis
    def get_sentiment_score():
        return np.random.uniform(-1, 1)  # Simulated score between -1 and 1

    sentiment_score = get_sentiment_score()
    sentiment_description = "Positive" if sentiment_score > 0 else "Negative" if sentiment_score < 0 else "Neutral"
    st.sidebar.write(f"Sentiment Score: {sentiment_score:.2f} ({sentiment_description})")

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
    related_symbols = ["USDCAD", "EURUSD", "GBPUSD", "WTICOUSD"]
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

    # If we have data, calculate correlation matrix
    if correlation_data:
        correlation_df = pd.DataFrame(correlation_data).corr()
        st.write("Correlation Matrix")
        st.write(correlation_df)
    else:
        st.write("Not enough data for correlation matrix.")

# Shutdown MT5 connection at the end
mt5.shutdown()

# Machine Learning Prediction (ARIMA Forecast)
# Prepare data for ARIMA
arima_df = df.set_index('time')['close']
arima_model = ARIMA(arima_df, order=(1, 1, 1))
arima_result = arima_model.fit()
predictions = arima_result.forecast(steps=50)  # 5-step forecast
predicted_values = predictions.values

fig_arima = go.Figure()
fig_arima.add_trace(go.Scatter(x=arima_df.index, y=arima_df, mode="lines", name="Actual"))
fig_arima.add_trace(go.Scatter(
    x=[arima_df.index[-1] + timedelta(hours=i+1) for i in range(len(predicted_values))],
    y=predicted_values, mode="lines", name="Forecast"))
fig_arima.update_layout(title="ARIMA Forecast", xaxis_title="Time", yaxis_title="Price", template="plotly_dark")
st.plotly_chart(fig_arima, use_container_width=True)

# Session-Based Highlighting
sessions = {'Tokyo': ('00:00', '09:00'), 'London': ('08:00', '17:00'), 'New York': ('13:00', '22:00')}
fig_sessions = go.Figure(data=[go.Candlestick(
    x=df['time'], open=df['open'], high=df['high'], low=df['low'], close=df['close'],
    increasing_line_color='cyan', decreasing_line_color='magenta'
)])

for session, (start, end) in sessions.items():
    session_start = pd.to_datetime(df['time'].dt.strftime(f'%Y-%m-%d {start}'))
    session_end = pd.to_datetime(df['time'].dt.strftime(f'%Y-%m-%d {end}'))
    fig_sessions.add_vrect(x0=session_start[0], x1=session_end[0], fillcolor="LightSalmon", opacity=0.2, layer="below", line_width=0)
fig_sessions.update_layout(title="Candlestick Chart with Market Sessions", template="plotly_dark")
st.plotly_chart(fig_sessions, use_container_width=True)

