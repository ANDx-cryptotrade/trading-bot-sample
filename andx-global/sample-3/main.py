"""Minimal ANDX derivatives example: check the margin required, place one order, show the position."""

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

AUTH_GRAPHQL_URL = os.getenv("ANDX_GRAPHQL_URL", "https://vakotrade-andx.cryptosrvc.com/graphql")
MARGIN_GRAPHQL_URL = os.getenv("ANDX_MARGIN_URL", "https://margin-trading-service-andx.cryptosrvc.com/graphql")

INSTRUMENT = os.getenv("INSTRUMENT", "BTCUSDT")
SIDE = os.getenv("SIDE", "buy")
QUANTITY = float(os.getenv("QUANTITY", 0.0001))
LEVERAGE = int(os.getenv("LEVERAGE", 1))


def authenticate():
    query = """
    mutation ($service_api_key: String!, $service_api_secret: String!) {
      service_signin(
        service_api_key: $service_api_key
        service_api_secret: $service_api_secret
      ) {
        jwt
        expires_at
      }
    }
    """

    r = requests.post(
        AUTH_GRAPHQL_URL,
        headers={"Content-Type": "application/json"},
        json={
            "query": query,
            "variables": {
                "service_api_key": os.getenv("ANDX_API_KEY"),
                "service_api_secret": os.getenv("ANDX_API_SECRET"),
            },
        },
    )

    r.raise_for_status()
    return r.json()["data"]["service_signin"]["jwt"]


access_token = authenticate()
headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


# 1. how much margin would this order need?

query = """
query ($instrument_id: String!, $quantity: Float!, $leverage: Int!, $side: MarginPositionSide!) {
  estimate_margin_user_position(
    instrument_id: $instrument_id
    quantity: $quantity
    leverage: $leverage
    side: $side
  ) {
    max_position_size
    order_required_margin
  }
}
"""

r = requests.post(
    MARGIN_GRAPHQL_URL,
    headers=headers,
    json={
        "query": query,
        "variables": {
            "instrument_id": INSTRUMENT,
            "quantity": QUANTITY,
            "leverage": LEVERAGE,
            "side": SIDE,
        },
    },
)

print("ESTIMATE", r.status_code)
print(json.dumps(r.json(), indent=2))


# 2. place the order

query = """
mutation ($instrument_id: String!, $quantity: Float!, $leverage: Int!,
          $side: MarginPositionSide!, $type: MarginOrderType!) {
  create_margin_order(
    instrument_id: $instrument_id
    quantity: $quantity
    leverage: $leverage
    side: $side
    type: $type
  ) {
    margin_order_id
  }
}
"""

r = requests.post(
    MARGIN_GRAPHQL_URL,
    headers=headers,
    json={
        "query": query,
        "variables": {
            "instrument_id": INSTRUMENT,
            "quantity": QUANTITY,
            "leverage": LEVERAGE,
            "side": SIDE,
            "type": "market",
        },
    },
)

print("\nORDER", r.status_code)
print(json.dumps(r.json(), indent=2))


# 3. Position details

query = """
query ($pager: PagerInput) {
  open_margin_positions(pager: $pager) {
    margin_position_id
    instrument_id
    side
    leverage
    amount
    entry_price
    pnl
  }
}
"""

r = requests.post(
    MARGIN_GRAPHQL_URL,
    headers=headers,
    json={"query": query, "variables": {"pager": {"offset": 0, "limit": 101}}},
)

print("\nOPEN POSITIONS", r.status_code)
print(json.dumps(r.json(), indent=2))
