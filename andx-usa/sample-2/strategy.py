"""ema_rsi strategy: buy an oversold dip within an uptrend; exit on ATR take-profit / stop-loss.

Self-contained: owns its params, indicator math (via `ta`), and the BUY / SELL / HOLD decision.
A trimmed single-coin version of btc_bot/live/strategies/ema_rsi.py.
"""

from dataclasses import dataclass

import ta

WARMUP = 150          # bars of history needed before EMA / RSI / ATR are trustworthy

# Strategy params: EMA window periods, RSI buy level, ATR period, and ATR exit multiples.
PARAMS = dict(ema_fast=12, ema_slow=26, rsi_period=14, rsi_buy=40, atr_period=14, tp_mult=3.0, sl_mult=1.5)


@dataclass
class Decision:
    action: str            # BUY / SELL / HOLD
    price: float           # latest price, for logging
    tp_price: float = 0.0  # take-profit, set on a BUY
    sl_price: float = 0.0  # stop-loss, set on a BUY
    note: str = ""         # human-readable reason


def decide(df, state):
    """Return a BUY / SELL / HOLD Decision for the latest bar."""
    close, high, low = df["close"], df["high"], df["low"]
    price = float(close.iloc[-1])

    # Holding -> exit when price hits the take-profit or stop-loss set at entry.
    if state.get("position") == "LONG":
        tp_price = float(state.get("tp_price") or 0)
        sl_price = float(state.get("sl_price") or 0)
        if price >= tp_price:
            decision = Decision("SELL", price, note="take-profit hit")
        elif price <= sl_price:
            decision = Decision("SELL", price, note="stop-loss hit")
        else:
            decision = Decision("HOLD", price, note="holding within exit bands")
        return decision

    # Flat -> buy an oversold dip inside an uptrend.
    ema_fast = ta.trend.ema_indicator(close, window=PARAMS["ema_fast"]).iloc[-1]
    ema_slow = ta.trend.ema_indicator(close, window=PARAMS["ema_slow"]).iloc[-1]
    rsi = ta.momentum.rsi(close, window=PARAMS["rsi_period"]).iloc[-1]
    atr = ta.volatility.AverageTrueRange(high=high, low=low, close=close,
                                         window=PARAMS["atr_period"]).average_true_range().iloc[-1]

    uptrend = ema_fast > ema_slow
    oversold = rsi < PARAMS["rsi_buy"]
    if uptrend and oversold and atr > 0:
        tp_price = price + PARAMS["tp_mult"] * atr
        sl_price = price - PARAMS["sl_mult"] * atr
        decision = Decision("BUY", price, tp_price, sl_price, "uptrend + oversold dip")
    else:
        decision = Decision("HOLD", price, note="flat - waiting for a dip in an uptrend")
    return decision

