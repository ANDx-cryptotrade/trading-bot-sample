"""Sample 2: a strategy bot. Each run fetches hourly candles, runs the ema_rsi strategy,
and buys / sells on ANDX with a take-profit and stop-loss. Designed to run once per call
(e.g. hourly via cron); it remembers its open position in state.json between runs.

Run:  python main.py     (needs all five ANDX_* env vars set, in .env or the shell)
"""

import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
import feed
import strategy
from andx_api import ANDX, APIError

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")   # load .env by absolute path, so it works from any working dir (e.g. cron)

# What to trade and how much quote to spend per buy.
COIN = "BTC"
QUOTE = "USDT"
TRADE_USD = 7.00

# Where the open position is remembered between runs.
STATE_FILE = HERE / "state.json"


def build_client():
    """Construct the ANDX client from environment variables."""
    api = ANDX(
        os.environ.get("ANDX_USER_NAME", ""),
        os.environ.get("ANDX_TOKEN", ""),
        os.environ.get("ANDX_API_KEY", ""),
        os.environ.get("ANDX_API_SECRET", ""),
        os.environ.get("ANDX_PASSPHRASE", ""),
    )
    return api


def load_state():
    """Read the saved position, or a flat default on first run."""
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
    else:
        state = {"position": "FLAT", "entry_price": 0, "tp_price": 0, "sl_price": 0}
    return state


def save_state(state):
    """Persist the position for the next run."""
    STATE_FILE.write_text(json.dumps(state, indent=2))


def confirm_status(api, order_number, tries=5):
    """Poll an order until it settles to F/C; return the last status seen."""
    status = "?"
    for _ in range(tries):
        try:
            status = api.get_order_status(order_number)
        except APIError:
            status = "?"
        if status in ("F", "C"):
            break
        time.sleep(1)
    return status


def execute_buy(api, decision):
    """Spend TRADE_USD of QUOTE on COIN; confirm the fill; return the order number."""
    quote = api.get_quote(COIN, QUOTE, f"{TRADE_USD:.2f}")
    order = api.place_instant_order(COIN, QUOTE, quote["sell_currency_amount"],
                                    quote["buy_currency_amount"], quote["visible_price"])
    order_number = order["order_number"]
    return order_number


def execute_sell(api):
    """Sell the whole COIN balance back to QUOTE; confirm the fill; return the order number."""
    sell_amount = api.get_available(COIN)
    quote = api.get_quote(QUOTE, COIN, f"{sell_amount:.8f}")
    order = api.place_instant_order(QUOTE, COIN, quote["sell_currency_amount"],
                                    quote["buy_currency_amount"], quote["visible_price"])
    order_number = order["order_number"]
    return order_number


def run():
    """One tick: load state -> fetch bars -> decide -> execute -> save state."""
    api = build_client()
    state = load_state()

    # Fetch enough hourly history to warm up the indicators.
    days = strategy.WARMUP // 24 + 3
    df = feed.recent_bars(COIN, days=days)
    if len(df) < strategy.WARMUP:
        print(f"warmup: {len(df)}/{strategy.WARMUP} bars - skipping")
        return

    # Ask the strategy what to do.
    decision = strategy.decide(df, state)
    print(f"{COIN}/{QUOTE} price: {decision.price:.2f}  pos: {state['position']}  -> {decision.action} ({decision.note})")

    # Enter a new long.
    if decision.action == "BUY" and state["position"] != "LONG":
        order_number = execute_buy(api, decision)
        status = confirm_status(api, order_number)
        print(f"BUY order {order_number} status: {status}")
        if status == "F":
            state = {"position": "LONG", "entry_price": decision.price,
                     "tp_price": decision.tp_price, "sl_price": decision.sl_price}
            save_state(state)

    # Exit the open long.
    elif decision.action == "SELL" and state["position"] == "LONG":
        order_number = execute_sell(api)
        status = confirm_status(api, order_number)
        print(f"SELL order {order_number} status: {status}")
        if status == "F":
            state = {"position": "FLAT", "entry_price": 0, "tp_price": 0, "sl_price": 0}
            save_state(state)


if __name__ == "__main__":
    try:
        run()
    except APIError as error:
        print(f"ANDX error: {error}")

