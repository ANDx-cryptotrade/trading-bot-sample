# andx_trading_bot_starter

The Beginner ANDX bot: check the price, place a fixed-amount buy, confirm the order status.

## Files
- `andx_api.py` — ANDX client (quote, place order, balance, order status).
- `strategy.py` — Trading logic. `TRADE_USD` defines the trade size per execution. Update the `decide()` function to implement your own buy/sell strategy.
- `main.py` — The main runner that ties together the trading logic and ANDX execution endpoints.

## Setup
```
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your credentials:
- `ANDX_USER_NAME` — account username
- `ANDX_TOKEN` — browser token (for placing orders)
- `ANDX_API_KEY`, `ANDX_API_SECRET`, `ANDX_PASSPHRASE` — API key (for order status)

( For details on obtaining the API keys and token, refer to STEP 2: https://andx.ai/set-up-a-bot )

`main.py` loads `.env` automatically, so you can just run `python main.py`. The
variables can also be set in the shell instead of a `.env` file.

## Run
```
python main.py     # places a live buy and polls the order status
```
Heads up: this places a **real order** on ANDX every run.

Sample output — order filled (`status: F`):
```
BTC/USDT price: 60029.15701912
decision: BUY (spend 7.00 USDT)
placed order 12345678
order 12345678 status: F
```

Sample output — order cancelled (`status: C`):
```
BTC/USDT price: 60139.52369497
decision: BUY (spend 5.00 USDT)
placed order 87654321
order 87654321 status: C
```

## More endpoints
This bot uses only a few ANDX endpoints (quote, place order, balance, order status).
For the full API — other endpoints, parameters, and auth details — see the docs at
[docs.andx.one](https://docs.andx.one).


