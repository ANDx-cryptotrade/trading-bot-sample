"""
Fetch recent hourly OHLCV data from Coinbase as a DataFrame for strategy signals.

Trade execution remains on ANDX using the sample-1 flow. Coinbase is used only
for public candle data.

"""

import time
from datetime import datetime, timezone
import pandas as pd
import requests

CANDLES_URL = "https://api.exchange.coinbase.com/products/{product}/candles"
GRANULARITY = 3600       # hourly bars, in seconds
MAX_CANDLES = 300        # Coinbase per-request cap; we page backwards past it


def _iso(unix_seconds):
    """Format unix seconds as the ISO 8601 UTC string Coinbase expects."""
    text = datetime.fromtimestamp(unix_seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return text


def _fetch_page(product, start, end):
    """Fetch one candle page for the [start, end] unix-second window; return row dicts."""
    params = {"granularity": GRANULARITY, "start": _iso(start), "end": _iso(end)}
    response = requests.get(CANDLES_URL.format(product=product), params=params, timeout=20)
    response.raise_for_status()
    payload = response.json()    # [[time, low, high, open, close, volume], ...] newest first
    rows = [{"timestamp": c[0], "open": c[3], "high": c[2], "low": c[1], "close": c[4], "volume": c[5]}
            for c in payload]
    return rows


def recent_bars(coin="BTC", days=10):
    """Return the most recent `days` of hourly Coinbase OHLCV candles for `coin` vs USD
    as a chronologically sorted DataFrame."""
    product = f"{coin}-USD"
    now = int(time.time())
    oldest = now - days * 86400
    span = MAX_CANDLES * GRANULARITY
    end = now
    collected = {}
    # Page backwards from now until we cover `days`.
    while end > oldest:
        rows = _fetch_page(product, end - span, end)
        if not rows:
            break
        for row in rows:
            collected[row["timestamp"]] = row    # dedupe overlapping page edges by timestamp
        end = end - span
        time.sleep(0.25)                          # stay within Coinbase's public rate limit
    ordered = sorted(collected.values(), key=lambda row: row["timestamp"])
    frame = pd.DataFrame([r for r in ordered if r["timestamp"] >= oldest])
    frame[["open", "high", "low", "close", "volume"]] = frame[["open", "high", "low", "close", "volume"]].astype(float)
    return frame

