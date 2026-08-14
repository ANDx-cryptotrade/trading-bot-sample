"""ANDX GraphQL API client: one function per endpoint, returning the raw response."""

# API reference: https://docs.andxus.io

import os

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

URL = os.environ.get("VAKO_GRAPHQL_URL", "https://vakotrade-andx.cryptosrvc.com/graphql")
TIMEOUT = 20


# ---- transport ----

def post(query, variables=None, token=None, name="call"):
    """Send one GraphQL call. Errors arrive with HTTP 200, so the body is checked."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.post(URL, json={"query": query, "variables": variables or {}},
                      headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        msg = body["errors"][0].get("message", body["errors"])
        raise RuntimeError(f"{name} failed: {msg} | sent {variables}")
    data = body["data"]
    return data


# ---- 1. LOGIN ----

LOGIN = """
mutation ($api_key: String!, $api_secret: String!) {
  service_signin(service_api_key: $api_key, service_api_secret: $api_secret) {
    jwt
    expires_at
  }
}
"""


def get_jwt():
    """Exchange the API credentials for a session JWT."""
    key = os.getenv("ANDX_API_KEY")
    secret = os.getenv("ANDX_API_SECRET")
    if not key or not secret:
        raise RuntimeError("ANDX_API_KEY and ANDX_API_SECRET are missing. Add them to the .env file.")
    data = post(LOGIN, variables={"api_key": key, "api_secret": secret}, name="service_signin")
    token = data["service_signin"]["jwt"]
    return token


# ---- 2. PRICE ----

PRICE = """
query ($instrument_id: String!) {
  instruments(instrument_id: $instrument_id) {
    instrument_id
    price {
      bid
      ask
      ts
    }
  }
}
"""


def get_price(instrument, token):
    """Return the current top of book: bid, ask and timestamp."""
    data = post(PRICE, variables={"instrument_id": instrument}, token=token, name="instruments")
    rows = data["instruments"]
    if not rows:
        raise RuntimeError(f"{instrument} not found on this exchange")
    book = rows[0].get("price") or {}
    return book


# ---- 3. PRICE BARS ----

PRICE_BARS = """
query ($instrument_id: String!, $limit: Int, $periodicity: InstrumentHistoryPeriodicity) {
  instrument_price_bars(instrument_id: $instrument_id, limit: $limit, periodicity: $periodicity) {
    ts
    open
    high
    low
    close
  }
}
"""


def get_bars(instrument, token, limit=200, periodicity="hour"):
    data = post(PRICE_BARS,
                variables={"instrument_id": instrument, "limit": limit, "periodicity": periodicity},
                token=token, name="instrument_price_bars")
    bars = data["instrument_price_bars"]
    return bars


# ---- 4. CREATE ORDER ----

CREATE_ORDER = """
mutation ($instrument_id: String!, $side: OrderSide!, $quantity: Float!, $quantity_mode: OrderQuantityMode) {
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


def create_order(instrument, side, quantity, mode, token):
    data = post(CREATE_ORDER,
                variables={"instrument_id": instrument, "side": side,
                           "quantity": float(quantity), "quantity_mode": mode},
                token=token, name="create_order")
    order = data["create_order"]
    return order


# ---- 5. CLOSED ORDERS ----

CLOSED_ORDERS = """
query ($instrument_id: String, $pager: PagerInput) {
  closed_orders(instrument_id: $instrument_id, pager: $pager) {
    order_id
    status
    executed_quantity
    quantity_mode
    price
    message
  }
}
"""


def get_closed_orders(token, instrument=None, limit=20):
    """Return recent finished orders, optionally filtered to one instrument."""
    data = post(CLOSED_ORDERS,
                variables={"instrument_id": instrument, "pager": {"limit": limit, "offset": 0}},
                token=token, name="closed_orders")
    orders = data["closed_orders"]
    return orders


# ---- 6. TRADING FEES ----

TRADING_FEES = """
query ($pager: PagerInput) {
  trading_fees(pager: $pager) {
    instrument_id
    maker_flat
    taker_flat
    maker_progressive
    taker_progressive
  }
}
"""


def get_trading_fees(token):
    data = post(TRADING_FEES,
                variables={"pager": {"limit": 1000, "offset": 0}},
                token=token, name="trading_fees")
    fees = data["trading_fees"]
    return fees


# ---- 7. BALANCES ----

BALANCES = """
query {
  accounts_balances {
    currency_id
    total_balance
    exposed_balance
    margin_exposure
    free_balance
  }
}
"""


def get_balances(token):
    data = post(BALANCES, token=token, name="accounts_balances")
    accounts = data["accounts_balances"]
    return accounts


# ---- 8. INSTRUMENTS ----

INSTRUMENTS = """
query {
  instruments {
    instrument_id
    min_quantity
    min_quote_quantity
    price_decimals
    quantity_decimals
    base_currency { precision }
    quote_currency { precision }
  }
}
"""


def get_instruments(token):
    data = post(INSTRUMENTS, token=token, name="instruments")
    rows = data["instruments"]
    return rows
