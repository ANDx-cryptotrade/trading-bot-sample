"""Minimal ANDX example: log in, place one market order and report the fill."""

import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

URL = os.getenv("ANDX_GRAPHQL_URL", "https://vakotrade-andx.cryptosrvc.com/graphql")

INSTRUMENT = os.getenv("INSTRUMENT", "BTCUSDT")
SIDE = os.getenv("SIDE", "buy")
QUANTITY = float(os.getenv("QUANTITY", 5))
MODE = os.getenv("MODE", "quote")


LOGIN = """
mutation ($key: String!, $secret: String!) {
  service_signin(service_api_key: $key, service_api_secret: $secret) {
    jwt
    expires_at
  }
}
"""

CREATE_ORDER = """
mutation ($instrument_id: String!, $side: OrderSide!, $quantity: Float!,
          $quantity_mode: OrderQuantityMode) {
  create_order(instrument_id: $instrument_id, type: market, side: $side, time_in_force: fok,
               quantity: $quantity, quantity_mode: $quantity_mode) {
    order_id
    status
    executed_quantity
    quantity_mode
    price
    message
  }
}
"""

CLOSED_ORDERS = """
query ($instrument_id: String!) {
  closed_orders(instrument_id: $instrument_id, pager: {limit: 20, offset: 0}) {
    order_id
    status
    executed_quantity
    quantity_mode
    price
    message
  }
}
"""


def post(query, variables=None, token=None):
    """Send one GraphQL call. Errors arrive with HTTP 200, so the body is checked."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.post(URL, json={"query": query, "variables": variables or {}},
                      headers=headers, timeout=20)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise SystemExit(f"API error: {body['errors'][0]['message']}")
    data = body["data"]
    return data


def wait_for_fill(instrument, order_id, token, seconds=30):
    """Poll closed_orders until the order appears, or give up."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        time.sleep(2)
        for row in post(CLOSED_ORDERS, {"instrument_id": instrument}, token)["closed_orders"]:
            if row["order_id"] == order_id:
                return row
    return None


def main():
    key, secret = os.getenv("ANDX_API_KEY"), os.getenv("ANDX_API_SECRET")
    if not key or not secret:
        raise SystemExit("Put ANDX_API_KEY and ANDX_API_SECRET in .env first")

    token = post(LOGIN, {"key": key, "secret": secret})["service_signin"]["jwt"]
    print("logged in")

    order = post(CREATE_ORDER, {"instrument_id": INSTRUMENT, "side": SIDE,
                                "quantity": float(QUANTITY), "quantity_mode": MODE}, token)["create_order"]
    print(f"placed {SIDE} {QUANTITY} ({MODE}) on {INSTRUMENT}")
    print(json.dumps(order, indent=2))

    filled = wait_for_fill(INSTRUMENT, order["order_id"], token)
    if not filled:
        raise SystemExit("order did not settle in 30s — check it manually before rerunning")

    print("\nfilled:")
    print(json.dumps(filled, indent=2))
    if filled["status"] != "completed":
        print(f"\nNOT filled — status {filled['status']}: {filled.get('message')}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        sys.exit(1)
