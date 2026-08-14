"""Beginner ANDX bot: check the price, place a fixed-amount buy, confirm the order status.

Run:  python main.py     (needs all five ANDX_* env vars set, in .env or the shell)
"""

import os
import time

from dotenv import load_dotenv

import strategy
from andx_api import ANDX, APIError

# Load credentials from a local .env file if present.
load_dotenv()

# What to trade.
COIN = "BTC"
QUOTE = "USDT"


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


def run():
    """One tick: price -> decide -> trade -> status."""
    api = build_client()

    # Check the price via an instant-trade quote.
    quote = api.get_quote(COIN, QUOTE, f"{strategy.TRADE_USD:.2f}")
    price = float(quote["visible_price"])
    print(f"{COIN}/{QUOTE} price: {price}")

    # Decide what to do.
    action = strategy.decide(price)
    print(f"decision: {action} (spend {strategy.TRADE_USD:.2f} {QUOTE})")
    if action != "BUY":
        return

    # Place the trade using the exact values from the fresh quote.
    order = api.place_instant_order(COIN, QUOTE, quote["sell_currency_amount"],
                                    quote["buy_currency_amount"], quote["visible_price"])
    order_number = order["order_number"]
    print(f"placed order {order_number}")

    # Check the order status.
    status = confirm_status(api, order_number)
    print(f"order {order_number} status: {status}")


if __name__ == "__main__":
    try:
        run()
    except APIError as error:
        print(f"ANDX error: {error}")

