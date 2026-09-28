import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator


def calculate_momentum_score(df):
    """
    Calculate a momentum score for one stock.

    Expected columns:
    date
    close
    volume
    """

    df = df.copy()

    if len(df) < 50:
        return None

    df = df.sort_values("date")

    # Moving averages
    df["ema20"] = EMAIndicator(
        close=df["close"],
        window=20
    ).ema_indicator()

    df["ema50"] = EMAIndicator(
        close=df["close"],
        window=50
    ).ema_indicator()

    # RSI
    df["rsi"] = RSIIndicator(
        close=df["close"],
        window=14
    ).rsi()

    # Returns
    df["return_20d"] = (
        df["close"].pct_change(20) * 100
    )

    df["return_50d"] = (
        df["close"].pct_change(50) * 100
    )

    latest = df.iloc[-1]

    score = 0

    # 20-day momentum
    if latest["return_20d"] > 10:
        score += 25
    elif latest["return_20d"] > 5:
        score += 15

    # 50-day momentum
    if latest["return_50d"] > 20:
        score += 25
    elif latest["return_50d"] > 10:
        score += 15

    # Trend
    if latest["close"] > latest["ema20"]:
        score += 10

    if latest["ema20"] > latest["ema50"]:
        score += 15

    # RSI
    if 55 <= latest["rsi"] <= 70:
        score += 15

    return {
        "score": score,
        "close": latest["close"],
        "rsi": latest["rsi"],
        "return_20d": latest["return_20d"],
        "return_50d": latest["return_50d"],
    }