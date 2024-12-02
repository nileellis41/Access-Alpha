import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

# Initialize MT5 and fetch forex data
def fetch_forex_data():
    if not mt5.initialize():
        st.error("Failed to initialize MetaTrader5")
        return None

    forex_pairs = ["EURUSD", "USDJPY", "GBPUSD", "USDCHF", "AUDUSD", "USDCAD"]
    forex_data = {}

    for pair in forex_pairs:
        rates = mt5.copy_rates_from_pos(pair, mt5.TIMEFRAME_H4, 0, 1000)
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df['returns'] = df['close'].pct_change()
        forex_data[pair] = df

    mt5.shutdown()
    return forex_data

# Function to calculate RSI
def calculate_rsi(data, period=14):
    delta = data['close'].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    
    avg_gain = pd.Series(gain).rolling(window=period).mean()
    avg_loss = pd.Series(loss).rolling(window=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# Fetch forex data and process RSI-based signals
st.title("Forex Pair Analysis - Various Indicators and Signals")
forex_data = fetch_forex_data()

if forex_data:
    # Calculate RSI and buy/sell signals for each pair
    for pair, data in forex_data.items():
        data['RSI'] = calculate_rsi(data)
        data['Buy_Signal'] = data['RSI'] < 30   # Buy when RSI is below 30
        data['Sell_Signal'] = data['RSI'] > 70  # Sell when RSI is above 70
        data['pair'] = pair  # Add pair identifier for consolidation

    # Consolidate all pairs' data into one DataFrame
    df = pd.concat(forex_data.values(), ignore_index=True)

# Function to plot close price
def plot_close_price(df, pair):
    pair_data = df[df['pair'] == pair]
    
    plt.style.use('dark_background')
    plt.figure(figsize=(14, 6))
    plt.plot(pair_data['time'], pair_data['close'], label='Close Price', color='cyan')
    plt.title(f'{pair} Close Price Over Time')
    plt.xlabel('Time')
    plt.ylabel('Price')
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    st.pyplot(plt)

# Function to plot moving averages
def plot_moving_averages(df, pair):
    pair_data = df[df['pair'] == pair]
    
    # Calculate moving averages if not already in data
    pair_data['MA_50'] = pair_data['close'].rolling(window=50).mean()
    pair_data['MA_200'] = pair_data['close'].rolling(window=200).mean()
    
    plt.style.use('dark_background')
    plt.figure(figsize=(14, 6))
    plt.plot(pair_data['time'], pair_data['close'], label='Close Price', color='cyan', alpha=0.5)
    plt.plot(pair_data['time'], pair_data['MA_50'], label='50-period MA', color='orange', linestyle='--')
    plt.plot(pair_data['time'], pair_data['MA_200'], label='200-period MA', color='purple', linestyle='--')
    plt.title(f'{pair} Moving Averages')
    plt.xlabel('Time')
    plt.ylabel('Price')
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    st.pyplot(plt)

# Define function to plot RSI-based strategy for each forex pair
def plot_rsi_analysis(df, pair):
    pair_data = df[df['pair'] == pair]

    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # Plot close price with buy and sell signals
    ax1.plot(pair_data['time'], pair_data['close'], label='Close Price', color='cyan', alpha=0.7)
    buy_signals = pair_data[pair_data['Buy_Signal']]
    sell_signals = pair_data[pair_data['Sell_Signal']]
    ax1.scatter(buy_signals['time'], buy_signals['close'], marker='^', color='green', label='Buy Signal', s=100)
    ax1.scatter(sell_signals['time'], sell_signals['close'], marker='v', color='red', label='Sell Signal', s=100)

    # Customize the price plot
    ax1.set_title(f'{pair} RSI-Based Strategy - Close Price and Signals')
    ax1.set_ylabel('Price')
    ax1.legend(loc='upper left')
    ax1.grid(True)

    # Plot RSI on a secondary axis
    ax2.plot(pair_data['time'], pair_data['RSI'], label='RSI', color='yellow', alpha=0.7)
    ax2.axhline(30, color='green', linestyle='--', label='Oversold (30)')
    ax2.axhline(70, color='red', linestyle='--', label='Overbought (70)')
    
    # Customize the RSI plot
    ax2.set_title('RSI Indicator')
    ax2.set_xlabel('Time')
    ax2.set_ylabel('RSI')
    ax2.legend(loc='upper left')
    ax2.grid(True)

    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)

# Separate sections for each type of analysis in Streamlit
if forex_data:
    # Section 1: Close Price Analysis
    st.header("Section 1: Close Price Analysis")
    pair_selection_close = st.selectbox("Select Forex Pair for Close Price Analysis", df['pair'].unique(), key="close_price")
    st.write(f"Displaying Close Price Analysis for {pair_selection_close}")
    plot_close_price(df, pair_selection_close)
    
    # Section 2: Moving Averages Analysis
    st.header("Section 2: Moving Averages Analysis")
    pair_selection_ma = st.selectbox("Select Forex Pair for Moving Averages", df['pair'].unique(), key="moving_average")
    st.write(f"Displaying Moving Averages Analysis for {pair_selection_ma}")
    plot_moving_averages(df, pair_selection_ma)
    
    # Section 3: RSI Analysis
    st.header("Section 3: RSI-Based Strategy")
    pair_selection_rsi = st.selectbox("Select Forex Pair for RSI-Based Analysis", df['pair'].unique(), key="rsi_analysis")
    st.write(f"Displaying RSI-Based Strategy for {pair_selection_rsi}")
    plot_rsi_analysis(df, pair_selection_rsi)

# Function to calculate Fibonacci retracement levels
def calculate_fibonacci_levels(data, lookback_period=100):
    recent_high = data['close'].rolling(window=lookback_period).max()
    recent_low = data['close'].rolling(window=lookback_period).min()

    data['Fib_23.6'] = recent_low + (recent_high - recent_low) * 0.236
    data['Fib_38.2'] = recent_low + (recent_high - recent_low) * 0.382
    data['Fib_50.0'] = recent_low + (recent_high - recent_low) * 0.5
    data['Fib_61.8'] = recent_low + (recent_high - recent_low) * 0.618
    data['Fib_76.4'] = recent_low + (recent_high - recent_low) * 0.764
    return data

# Fetch data and process Fibonacci levels and signals
forex_data = fetch_forex_data()
if forex_data:
    for pair, data in forex_data.items():
        data = calculate_fibonacci_levels(data)
        data['Buy_Signal'] = (data['close'] < data['Fib_76.4']) & (data['close'] > data['Fib_61.8'])
        data['Sell_Signal'] = (data['close'] > data['Fib_23.6']) & (data['close'] < data['Fib_38.2'])
        data['pair'] = pair
    df = pd.concat(forex_data.values(), ignore_index=True)

# Define the plot for Fibonacci retracement analysis
def plot_fibonacci_retracement(df, pair):
    pair_data = df[df['pair'] == pair]
    
    plt.style.use('dark_background')
    plt.figure(figsize=(14, 8))
    plt.plot(pair_data['time'], pair_data['close'], label='Close Price', color='cyan', alpha=0.7)
    plt.plot(pair_data['time'], pair_data['Fib_23.6'], label='Fib 23.6%', color='red', linestyle=':')
    plt.plot(pair_data['time'], pair_data['Fib_38.2'], label='Fib 38.2%', color='orange', linestyle=':')
    plt.plot(pair_data['time'], pair_data['Fib_50.0'], label='Fib 50.0%', color='yellow', linestyle=':')
    plt.plot(pair_data['time'], pair_data['Fib_61.8'], label='Fib 61.8%', color='green', linestyle=':')
    plt.plot(pair_data['time'], pair_data['Fib_76.4'], label='Fib 76.4%', color='blue', linestyle=':')
    
    # Mark buy/sell signals
    buy_signals = pair_data[pair_data['Buy_Signal']]
    sell_signals = pair_data[pair_data['Sell_Signal']]
    plt.scatter(buy_signals['time'], buy_signals['close'], marker='^', color='green', label='Buy Signal', s=100)
    plt.scatter(sell_signals['time'], sell_signals['close'], marker='v', color='red', label='Sell Signal', s=100)

    plt.title(f'{pair} Fibonacci Retracement Levels')
    plt.xlabel('Time')
    plt.ylabel('Price')
    plt.legend(loc='upper left')
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    st.pyplot(plt)

# Streamlit section for Fibonacci retracement analysis
if forex_data:
    st.header("Section 4: Fibonacci Retracement Analysis")
    pair_selection_fib = st.selectbox("Select Forex Pair for Fibonacci Analysis", df['pair'].unique(), key="fibonacci_analysis")
    st.write(f"Displaying Fibonacci Retracement Analysis for {pair_selection_fib}")
    plot_fibonacci_retracement(df, pair_selection_fib)

# Initialize MT5 and fetch forex data
def fetch_forex_data():
    if not mt5.initialize():
        st.error("Failed to initialize MetaTrader5")
        return None

    forex_pairs = ["EURUSD", "USDJPY", "GBPUSD", "USDCHF", "AUDUSD", "USDCAD"]
    forex_data = {}

    for pair in forex_pairs:
        rates = mt5.copy_rates_from_pos(pair, mt5.TIMEFRAME_H1, 0, 500)
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df['returns'] = df['close'].pct_change()
        forex_data[pair] = df

    mt5.shutdown()
    return forex_data

# Function to calculate Fibonacci retracement levels
def calculate_fibonacci_levels(data, lookback_period=100):
    recent_high = data['close'].rolling(window=lookback_period).max()
    recent_low = data['close'].rolling(window=lookback_period).min()
    data['Fib_23.6'] = recent_low + (recent_high - recent_low) * 0.236
    data['Fib_38.2'] = recent_low + (recent_high - recent_low) * 0.382
    data['Fib_50.0'] = recent_low + (recent_high - recent_low) * 0.5
    data['Fib_61.8'] = recent_low + (recent_high - recent_low) * 0.618
    data['Fib_76.4'] = recent_low + (recent_high - recent_low) * 0.764
    return data

# Function to calculate RSI
def calculate_rsi(data, period=14):
    delta = data['close'].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    
    avg_gain = pd.Series(gain).rolling(window=period).mean()
    avg_loss = pd.Series(loss).rolling(window=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# Fetch forex data and apply Fibonacci and RSI calculations
forex_data = fetch_forex_data()
if forex_data:
    for pair, data in forex_data.items():
        data = calculate_fibonacci_levels(data)
        data['RSI'] = calculate_rsi(data)
        data['Buy_Signal'] = (data['RSI'] < 30) & (data['close'] < data['Fib_61.8'])
        data['Sell_Signal'] = (data['RSI'] > 70) & (data['close'] > data['Fib_38.2'])
        data['pair'] = pair
    df = pd.concat(forex_data.values(), ignore_index=True)

# Plotting function for Fibonacci + RSI strategy
def plot_fibonacci_rsi(df, pair):
    pair_data = df[df['pair'] == pair]

    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # Plot close price with Fibonacci levels
    ax1.plot(pair_data['time'], pair_data['close'], label='Close Price', color='cyan', alpha=0.7)
    ax1.plot(pair_data['time'], pair_data['Fib_23.6'], label='Fib 23.6%', color='red', linestyle=':')
    ax1.plot(pair_data['time'], pair_data['Fib_38.2'], label='Fib 38.2%', color='orange', linestyle=':')
    ax1.plot(pair_data['time'], pair_data['Fib_50.0'], label='Fib 50.0%', color='yellow', linestyle=':')
    ax1.plot(pair_data['time'], pair_data['Fib_61.8'], label='Fib 61.8%', color='green', linestyle=':')
    ax1.plot(pair_data['time'], pair_data['Fib_76.4'], label='Fib 76.4%', color='blue', linestyle=':')

    # Mark Buy and Sell signals
    buy_signals = pair_data[pair_data['Buy_Signal']]
    sell_signals = pair_data[pair_data['Sell_Signal']]
    ax1.scatter(buy_signals['time'], buy_signals['close'], marker='^', color='green', label='Buy Signal', s=100)
    ax1.scatter(sell_signals['time'], sell_signals['close'], marker='v', color='red', label='Sell Signal', s=100)

    # Customize the price plot
    ax1.set_title(f'{pair} Fibonacci Retracement + RSI Strategy')
    ax1.set_ylabel('Price')
    ax1.legend(loc='upper left')
    ax1.grid(True)

    # Plot RSI on a secondary axis
    ax2.plot(pair_data['time'], pair_data['RSI'], label='RSI', color='yellow', alpha=0.7)
    ax2.axhline(30, color='green', linestyle='--', label='Oversold (30)')
    ax2.axhline(70, color='red', linestyle='--', label='Overbought (70)')
    
    # Customize the RSI plot
    ax2.set_title('RSI Indicator')
    ax2.set_xlabel('Time')
    ax2.set_ylabel('RSI')
    ax2.legend(loc='upper left')
    ax2.grid(True)

    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)

# Streamlit section for Fibonacci + RSI strategy
if forex_data:
    st.header("Section 5: Fibonacci + RSI Strategy")
    pair_selection_fib_rsi = st.selectbox("Select Forex Pair for Fibonacci + RSI Analysis", df['pair'].unique(), key="fibonacci_rsi")
    st.write(f"Displaying Fibonacci + RSI Strategy for {pair_selection_fib_rsi}")
    plot_fibonacci_rsi(df, pair_selection_fib_rsi)


# Backtesting function
def run_backtest(df, initial_balance=10000, risk_per_trade=1.00):
    balance = initial_balance
    position = None
    trade_log = []
    balance_over_time = [initial_balance]  # Track balance over time for equity curve

    for i in range(1, len(df)):
        row = df.iloc[i]
        previous_row = df.iloc[i - 1]

        # Check buy conditions
        if row['Buy_Signal'] and position is None:
            entry_price = row['close']
            position = 'long'
            trade_log.append({
                'Type': 'Buy',
                'Entry Price': entry_price,
                'Entry Time': row['time'],
                'Size': balance * risk_per_trade / entry_price
            })

        # Check sell conditions if a long position is open
        elif row['Sell_Signal'] and position == 'long':
            exit_price = row['close']
            trade_log[-1]['Exit Price'] = exit_price
            trade_log[-1]['Exit Time'] = row['time']
            trade_log[-1]['Profit'] = (exit_price - trade_log[-1]['Entry Price']) * trade_log[-1]['Size']
            balance += trade_log[-1]['Profit']
            balance_over_time.append(balance)
            position = None

    trades_df = pd.DataFrame(trade_log)

    # Calculate performance metrics
    total_profit = trades_df['Profit'].sum() if 'Profit' in trades_df else 0
    win_rate = len(trades_df[trades_df['Profit'] > 0]) / len(trades_df) if len(trades_df) > 0 else 0
    max_drawdown = (initial_balance - min(balance_over_time)) / initial_balance
    sharpe_ratio = (trades_df['Profit'].mean() / trades_df['Profit'].std()) * (252 ** 0.5) if len(trades_df) > 1 else 0
    average_profit = trades_df['Profit'].mean() if len(trades_df) > 0 else 0
    num_trades = len(trades_df)

    return {
        'Total Profit': total_profit,
        'Win Rate': win_rate,
        'Max Drawdown': max_drawdown,
        'Sharpe Ratio': sharpe_ratio,
        'Average Profit': average_profit,
        'Number of Trades': num_trades,
        'Balance Over Time': balance_over_time,
        'Trade Log': trades_df
    }

# Fetch forex data and apply calculations
forex_data = fetch_forex_data()
if forex_data:
    for pair, data in forex_data.items():
        data = calculate_fibonacci_levels(data)
        data['RSI'] = calculate_rsi(data)
        data['Buy_Signal'] = (data['RSI'] < 20) 
        data['Sell_Signal'] = (data['RSI'] > 80)
        data['pair'] = pair
    df = pd.concat(forex_data.values(), ignore_index=True)

# Streamlit section for backtesting
if forex_data:
    st.header("Section 6: Backtesting")
    pair_selection_backtest = st.selectbox("Select Forex Pair for Backtesting", df['pair'].unique(), key="backtest")
    filtered_df = df[df['pair'] == pair_selection_backtest]

    # Run backtest on selected pair
    results = run_backtest(filtered_df)

    # Display results
    st.write(f"**Total Profit:** ${results['Total Profit']:.2f}")
    st.write(f"**Win Rate:** {results['Win Rate'] * 100:.2f}%")
    st.write(f"**Max Drawdown:** {results['Max Drawdown'] * 100:.2f}%")
    st.write(f"**Sharpe Ratio:** {results['Sharpe Ratio']:.2f}")
    st.write(f"**Average Profit per Trade:** ${results['Average Profit']:.2f}")
    st.write(f"**Number of Trades:** {results['Number of Trades']}")

    # Display trade log
    if not results['Trade Log'].empty:
        st.write("**Trade Log:**")
        st.dataframe(results['Trade Log'])

    # Plot equity curve
    st.write("**Equity Curve:**")
    plt.figure(figsize=(10, 5))
    plt.plot(results['Balance Over Time'], label="Equity Curve")
    plt.title(f"Equity Curve for {pair_selection_backtest}")
    plt.xlabel("Trade Number")
    plt.ylabel("Balance (USD)")
    plt.legend()
    plt.grid(True)
    st.pyplot(plt)

    # Plot profit distribution
    if not results['Trade Log'].empty and 'Profit' in results['Trade Log']:
        st.write("**Profit Distribution:**")
        plt.figure(figsize=(10, 5))
        plt.hist(results['Trade Log']['Profit'], bins=20, color='skyblue', edgecolor='black')
        plt.title("Profit Distribution")
        plt.xlabel("Profit per Trade (USD)")
        plt.ylabel("Frequency")
        st.pyplot(plt)

# Function to calculate moving averages and generate signals
def calculate_moving_averages(data):
    data['MA_30'] = data['close'].rolling(window=30).mean()
    data['MA_90'] = data['close'].rolling(window=90).mean()
    data['Buy_Signal_MA'] = (data['MA_30'] > data['MA_90']) & (data['MA_30'].shift(1) <= data['MA_90'].shift(1))
    data['Sell_Signal_MA'] = (data['MA_30'] < data['MA_90']) & (data['MA_30'].shift(1) >= data['MA_90'].shift(1))
    return data

# Apply moving average calculations
if forex_data:
    for pair, data in forex_data.items():
        data = calculate_moving_averages(data)
        data['pair'] = pair
    df = pd.concat(forex_data.values(), ignore_index=True)

# Backtesting the moving average strategy
def run_backtest_moving_avg(df, initial_balance=10000, risk_per_trade=1.00):
    balance = initial_balance
    position = None
    trade_log = []
    balance_over_time = [initial_balance]

    for i in range(1, len(df)):
        row = df.iloc[i]
        previous_row = df.iloc[i - 1]

        # Check buy condition
        if row['Buy_Signal_MA'] and position is None:
            entry_price = row['close']
            position = 'long'
            trade_log.append({
                'Type': 'Buy',
                'Entry Price': entry_price,
                'Entry Time': row['time'],
                'Size': balance * risk_per_trade / entry_price
            })

        # Check sell condition
        elif row['Sell_Signal_MA'] and position == 'long':
            exit_price = row['close']
            trade_log[-1]['Exit Price'] = exit_price
            trade_log[-1]['Exit Time'] = row['time']
            trade_log[-1]['Profit'] = (exit_price - trade_log[-1]['Entry Price']) * trade_log[-1]['Size']
            balance += trade_log[-1]['Profit']
            balance_over_time.append(balance)
            position = None

    trades_df = pd.DataFrame(trade_log)

    return {
        'Total Profit': trades_df['Profit'].sum(),
        'Win Rate': len(trades_df[trades_df['Profit'] > 0]) / len(trades_df) if len(trades_df) > 0 else 0,
        'Max Drawdown': (initial_balance - min(balance_over_time)) / initial_balance,
        'Number of Trades': len(trades_df),
        'Trade Log': trades_df,
        'Balance Over Time': balance_over_time
    }

# Streamlit Section for Moving Average Backtesting
if forex_data:
    st.header("Section 7: Moving Average 30/90 Strategy Backtesting")
    pair_selection_ma_backtest = st.selectbox("Select Forex Pair for MA Backtesting", df['pair'].unique(), key="ma_backtest")
    filtered_ma_df = df[df['pair'] == pair_selection_ma_backtest]

    # Run MA backtest on selected pair
    ma_results = run_backtest_moving_avg(filtered_ma_df)

    # Display results
    st.write(f"**Total Profit:** ${ma_results['Total Profit']:.2f}")
    st.write(f"**Win Rate:** {ma_results['Win Rate'] * 100:.2f}%")
    st.write(f"**Max Drawdown:** {ma_results['Max Drawdown'] * 100:.2f}%")
    st.write(f"**Number of Trades:** {ma_results['Number of Trades']}")

    # Display trade log
    if not ma_results['Trade Log'].empty:
        st.write("**Trade Log:**")
        st.dataframe(ma_results['Trade Log'])

    # Plot equity curve
    st.write("**Equity Curve:**")
    plt.figure(figsize=(10, 5))
    plt.plot(ma_results['Balance Over Time'], label="Equity Curve")
    plt.title(f"Equity Curve for {pair_selection_ma_backtest} (MA 30/90)")
    plt.xlabel("Trade Number")
    plt.ylabel("Balance (USD)")
    plt.legend()
    plt.grid(True)
    st.pyplot(plt)