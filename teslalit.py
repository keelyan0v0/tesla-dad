# -*- coding: utf-8 -*-
"""
Created on Sun Apr  5 21:05:21 2026

@author: killi
"""

import streamlit as st
import pandas as pd
import numpy as np
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# =============================
# CONFIG
# =============================
API_KEY = "PKNNUMQRVO2V5Q7HUKC46GFKVR"
SECRET_KEY = "CyYqXHDoq2tkrmQDG5Gs1SjdrqJFbAYJ7FUq5gnRTVcM"

client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

# =============================
# STREAMLIT UI
# =============================
st.title("📈 Algo Backtester (Alpaca Powered)")

ticker = st.text_input("Ticker", "TSLA")
interval = st.selectbox("Timeframe", ["1Min", "5Min", "15Min", "30Min", "1Hour"])
capital = st.number_input("Starting Capital", 100, 10000, 220)
leverage = st.slider("Leverage", 1, 20, 1)

ema_fast = st.slider("EMA Fast", 5, 20, 7)
ema_slow = st.slider("EMA Slow", 10, 50, 25)
ema_exit = st.slider("EMA Exit", 20, 100, 35)

trail_trigger = st.slider("Trail Trigger (%)", 0.0, 0.1, 0.02)
trail_stop = st.slider("Trail Stop (%)", 0.0, 0.05, 0.01)

# =============================
# GET DATA (ALPACA)
# =============================
def get_data():
    timeframe_map = {
        "1Min": TimeFrame.Minute,
        "5Min": TimeFrame.Minute,
        "15Min": TimeFrame.Minute,
        "30Min": TimeFrame.Minute,
        "1Hour": TimeFrame.Hour
    }

    request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=timeframe_map[interval],
        limit=1000
    )

    bars = client.get_stock_bars(request).df

    df = bars.reset_index()
    df = df[df["symbol"] == ticker]

    df.rename(columns={
        "close": "Close",
        "timestamp": "time"
    }, inplace=True)

    return df

# =============================
# INDICATORS
# =============================
def add_indicators(df):
    df["EMA_fast"] = df["Close"].ewm(span=ema_fast).mean()
    df["EMA_slow"] = df["Close"].ewm(span=ema_slow).mean()
    df["EMA_exit"] = df["Close"].ewm(span=ema_exit).mean()
    return df

# =============================
# STRATEGY
# =============================
def add_strategy(df):
    df["Signal"] = 0

    cross_down = (
        (df["EMA_fast"].shift(1) > df["EMA_slow"].shift(1)) &
        (df["EMA_fast"] < df["EMA_slow"])
    )

    cross_up = (
        (df["EMA_fast"].shift(1) < df["EMA_exit"].shift(1)) &
        (df["EMA_fast"] > df["EMA_exit"])
    )

    df.loc[cross_down, "Signal"] = -1
    df.loc[cross_up, "Signal"] = 2

    return df

# =============================
# BACKTEST
# =============================
def backtest(df):
    capital_local = capital
    position = 0
    entry_price = 0
    peak_profit = 0

    returns = []
    trades = []

    for i in range(len(df)):
        price = df["Close"].iloc[i]
        signal = df["Signal"].iloc[i]

        if position == 0:
            if signal == -1:
                position = -1
                entry_price = price
                peak_profit = 0

            returns.append(0)

        else:
            pnl = (entry_price - price) / entry_price
            peak_profit = max(peak_profit, pnl)
            trailing_stop = peak_profit - trail_stop

            if pnl <= trailing_stop and peak_profit > trail_trigger:
                leveraged = pnl * leverage
                capital_local *= (1 + leveraged)

                trades.append(pnl)
                returns.append(leveraged)
                position = 0

            elif signal == 2:
                leveraged = pnl * leverage
                capital_local *= (1 + leveraged)

                trades.append(pnl)
                returns.append(leveraged)
                position = 0

            else:
                returns.append(0)

    df["strategy_returns"] = returns
    df["strategy_cumulative"] = (1 + df["strategy_returns"]).cumprod()

    return df, trades, capital_local

# =============================
# METRICS
# =============================
def metrics(df, trades, final_capital):
    strategy_return = df['strategy_cumulative'].iloc[-1]
    buy_hold = (df['Close'].iloc[-1] / df['Close'].iloc[0]) - 1

    win_rate = (np.array(trades) > 0).mean() * 100 if len(trades) > 0 else 0

    return pd.DataFrame({
        "Metric": [
            "Final Capital",
            "Strategy Return %",
            "Buy Hold %",
            "Trades",
            "Win Rate %"
        ],
        "Value": [
            round(final_capital, 2),
            round(strategy_return * 100, 2),
            round(buy_hold * 100, 2),
            len(trades),
            round(win_rate, 2)
        ]
    })

# =============================
# RUN BUTTON
# =============================
if st.button("Run Backtest"):

    df = get_data()
    df = add_indicators(df)
    df = add_strategy(df)

    df, trades, final_capital = backtest(df)

    results = metrics(df, trades, final_capital)

    st.subheader("📊 Results")
    st.dataframe(results)

    st.subheader("📈 Equity Curve")
    st.line_chart(df["strategy_cumulative"])

    st.subheader("📉 Price Chart")
    st.line_chart(df["Close"])