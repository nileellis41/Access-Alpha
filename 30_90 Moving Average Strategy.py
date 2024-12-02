import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

# Initialize MT5
if not mt5.initialize():
    st.error("Failed to initialize MetaTrader5")
    st.stop()

# Fetch historical data
def fetch_mt5_data(symbol, timeframe, num_bars):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_bars)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

# Add moving averages and signals
def calculate_signals(data):
    data['MA_30'] = data['close'].rolling(window=30).mean()
    data['MA_90'] = data['close'].rolling(window=90).mean()
    data['Buy_Signal'] = (data['MA_30'] > data['MA_90']) & (data['MA_30'].shift(1) <= data['MA_90'].shift(1))
    data['Sell_Signal'] = (data['MA_30'] < data['MA_90']) & (data['MA_30'].shift(1) >= data['MA_90'].shift(1))
    return data

# Unified backtest function with TP and SL
def run_backtest(data, initial_balance=10000, lot_size=0.1, stop_loss_pips=50, take_profit_pips=100):
    balance = initial_balance
    trade_log = []
    balance_over_time = [initial_balance]
    pip_value = 10  # Standard pip value for a lot size of 1

    for i in range(1, len(data)):
        row = data.iloc[i]

        # Process Buy Signal
        if row['Buy_Signal']:
            entry_price = row['close']
            stop_loss = entry_price - (stop_loss_pips * 0.0001)
            take_profit = entry_price + (take_profit_pips * 0.0001)
            trade_log.append({
                'Type': 'Buy',
                'Entry Price': entry_price,
                'Stop Loss': stop_loss,
                'Take Profit': take_profit,
                'Entry Time': row['time'],
                'Size': lot_size
            })

        # Process Sell Signal
        if row['Sell_Signal']:
            entry_price = row['close']
            stop_loss = entry_price + (stop_loss_pips * 0.0001)
            take_profit = entry_price - (take_profit_pips * 0.0001)
            trade_log.append({
                'Type': 'Sell',
                'Entry Price': entry_price,
                'Stop Loss': stop_loss,
                'Take Profit': take_profit,
                'Entry Time': row['time'],
                'Size': lot_size
            })

        # Update trades and check for exits
        for trade in trade_log:
            if 'Exit Price' not in trade:  # Active trade
                if trade['Type'] == 'Buy':
                    if row['low'] <= trade['Stop Loss']:  # Stop Loss
                        trade['Exit Price'] = trade['Stop Loss']
                    elif row['high'] >= trade['Take Profit']:  # Take Profit
                        trade['Exit Price'] = trade['Take Profit']

                elif trade['Type'] == 'Sell':
                    if row['high'] >= trade['Stop Loss']:  # Stop Loss
                        trade['Exit Price'] = trade['Stop Loss']
                    elif row['low'] <= trade['Take Profit']:  # Take Profit
                        trade['Exit Price'] = trade['Take Profit']

                # If trade has exited, log profit
                if 'Exit Price' in trade:
                    trade['Exit Time'] = row['time']
                    trade['Profit in Pips'] = ((trade['Exit Price'] - trade['Entry Price']) / 0.0001
                                               if trade['Type'] == 'Buy'
                                               else (trade['Entry Price'] - trade['Exit Price']) / 0.0001)
                    trade['Profit in USD'] = trade['Profit in Pips'] * pip_value * lot_size
                    balance += trade['Profit in USD']
                    balance_over_time.append(balance)

    trades_df = pd.DataFrame(trade_log)

    return {
        'Total Profit (USD)': trades_df['Profit in USD'].sum() if 'Profit in USD' in trades_df else 0,
        'Total Profit (Pips)': trades_df['Profit in Pips'].sum() if 'Profit in Pips' in trades_df else 0,
        'Number of Trades': len(trades_df),
        'Trade Log': trades_df,
        'Balance Over Time': balance_over_time
    }

# Streamlit UI and execution
symbol = st.sidebar.selectbox("Select Forex Pair", ["EURUSD", "USDJPY", "GBPUSD", "USDCAD", "AUDUSD", "USDCHF"])
timeframe = mt5.TIMEFRAME_H4
num_bars = 10000

data = fetch_mt5_data(symbol, timeframe, num_bars)
data = calculate_signals(data)

results = run_backtest(data, stop_loss_pips=50, take_profit_pips=100)

st.header(f"Backtesting {symbol} - 30/90 Moving Average Strategy with TP and SL")
st.write(f"**Total Profit (USD):** ${results['Total Profit (USD)']:.2f}")
st.write(f"**Total Profit (Pips):** {results['Total Profit (Pips)']:.2f} pips")
st.write(f"**Number of Trades:** {results['Number of Trades']}")

if not results['Trade Log'].empty:
    st.write("**Trade Log:**")
    st.dataframe(results['Trade Log'])

st.write("**Equity Curve:**")
plt.figure(figsize=(10, 5))
plt.plot(results['Balance Over Time'], label="Equity Curve")
plt.title(f"Equity Curve for {symbol}")
plt.xlabel("Trade Number")
plt.ylabel("Balance (USD)")
plt.legend()
plt.grid(True)
st.pyplot(plt)

import mplfinance as mpf

def plot_candlestick_with_signals(data, trade_log, title="Candlestick Chart with Buy/Sell Signals"):
    """
    Plot candlestick chart with buy and sell signals.
    """
    # Prepare data for mplfinance
    df = data[['time', 'open', 'high', 'low', 'close']].copy()
    df.set_index('time', inplace=True)

    # Prepare buy and sell markers
    buys = [trade for trade in trade_log if trade['Type'] == 'Buy']
    sells = [trade for trade in trade_log if trade['Type'] == 'Sell']

    buy_markers = pd.DataFrame(buys)
    sell_markers = pd.DataFrame(sells)

    # Convert times to the index format
    buy_markers['time'] = pd.to_datetime(buy_markers['Entry Time'])
    sell_markers['time'] = pd.to_datetime(sell_markers['Entry Time'])

    # Create scatter data for buy and sell signals
    scatter_buy = {
        'x': buy_markers['time'].values,
        'y': buy_markers['Entry Price'].values,
        'marker': '^',
        'color': 'green',
        's': 100,
        'label': 'Buy Signal'
    }

    scatter_sell = {
        'x': sell_markers['time'].values,
        'y': sell_markers['Entry Price'].values,
        'marker': 'v',
        'color': 'red',
        's': 100,
        'label': 'Sell Signal'
    }

    # Plot candlestick chart
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(14, 8))
    mpf.plot(df, type='candle', ax=ax, style='charles')

    # Add buy and sell markers
    ax.scatter(**scatter_buy)
    ax.scatter(**scatter_sell)

    # Add labels and legend
    ax.set_title(title, fontsize=16)
    ax.set_ylabel('Price', fontsize=12)
    ax.set_xlabel('Time', fontsize=12)
    ax.legend(loc='upper left')
    plt.xticks(rotation=45)
    plt.grid(True)
    st.pyplot(fig)

# Display candlestick chart with buy and sell signals
if not results['Trade Log'].empty:
    st.header("Candlestick Chart with Buy/Sell Signals")
    plot_candlestick_with_signals(data, results['Trade Log'].to_dict('records'))

