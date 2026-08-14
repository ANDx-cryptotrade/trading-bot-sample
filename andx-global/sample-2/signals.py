"""Indicators: trend() scores a coin for entry, risk_off() reports whether BTC is in a downtrend."""

import pandas as pd
import ta

EMA_LEN = 48
ADX_LEN = 14
ATR_LEN = 14


def _frame(bars):
    """Convert bars to a DataFrame, oldest first, dropping the still-forming last bar."""
    rows = sorted(bars, key=lambda b: b["ts"])[:-1]
    df = pd.DataFrame([{k: float(r[k]) for k in ("open", "high", "low", "close")} for r in rows])
    return df


def trend(bars):
    """Return (uptrend, adx, atr_pct), or (False, None, None) without enough history."""
    df = _frame(bars)
    if len(df) < EMA_LEN + ADX_LEN + 3:
        return (False, None, None)
    last = df["close"].iloc[-1]
    ema = ta.trend.EMAIndicator(df["close"], window=EMA_LEN).ema_indicator().iloc[-1]
    adx = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=ADX_LEN).adx().iloc[-1]
    atr = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=ATR_LEN)
    atr_pct = atr.average_true_range().iloc[-1] / last
    out = (bool(last > ema), float(adx), float(atr_pct))
    return out


def risk_off(bars):
    """Return True when BTC is below its 8h EMA or its 3h momentum is negative."""
    df = _frame(bars)
    if len(df) < 12:
        return False
    close = df["close"]
    last = close.iloc[-1]
    ema8 = ta.trend.EMAIndicator(close, window=8).ema_indicator().iloc[-1]
    off = bool(last < ema8 or last / close.iloc[-4] - 1 < 0)
    return off
