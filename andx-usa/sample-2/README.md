# sample-2 — strategy bot (ema_rsi with take-profit / stop-loss)

Sample-1 was about getting a single trade onto ANDX — authenticating with your token
and API key and confirming the order.
Sample-2 adds the missing piece: a **strategy**
that decides *when* to buy and sell, then places the trade. It buys an **oversold dip
inside an uptrend** (EMA + RSI) and exits on an ATR-based **take-profit** or **stop-loss**.
It runs once per call and remembers its open position between runs, so it's meant to be
scheduled (e.g. hourly via cron).

## Files
- `andx_api.py` — ANDX client (quote, place order, balance, order status).
- `feed.py` — fetches hourly OHLCV candles from Coinbase (for the indicators).
- `strategy.py` — the ema_rsi logic. `PARAMS` holds the tunables; `decide()` returns BUY / SELL / HOLD.
- `main.py` — the runner: load state → fetch candles → decide → trade → save state.
- `state.json` — created at runtime; holds the open position (gitignored).


## How it trades
- **Flat:** buys `TRADE_USD` of `COIN` when fast EMA > slow EMA *and* RSI is oversold.
  On entry it sets a take-profit (`+3 × ATR`) and stop-loss (`−1.5 × ATR`).
- **Long:** sells the whole position when price hits the take-profit or stop-loss.
- Otherwise it holds. Edit `COIN`, `QUOTE`, `TRADE_USD` in `main.py` and `PARAMS` in `strategy.py`.

## Setup
```
pip install -r requirements.txt
```
Copy `.env.example` to `.env` and fill in your credentials (same five `ANDX_*` vars
as sample-1; see STEP 2 at https://andx.ai/set-up-a-bot).

## Run once
```
python main.py
```
Sample output (a tick that decides to hold):
```
BTC/USDT price: 60139.52  pos: FLAT  -> HOLD (flat - waiting for a dip in an uptrend)
```
Heads up: a BUY or SELL places a **real order** on ANDX.

## Schedule it (cron, Linux/macOS)
The bot does one tick per run; cron repeats it. Run `crontab -e` and add one line to
run it at the top of every hour (adjust the path; use your venv's python if you have one):
```
0 * * * * /usr/bin/python3 /home/youruser/trading-bot-samples/sample-2/main.py >> /home/youruser/trading-bot-samples/sample-2/bot.log 2>&1
```
`main.py` finds its own `.env` and `state.json` by absolute path, so it doesn't matter
that cron runs from your home directory. Output is appended to `bot.log`.

### On Windows
Windows has no cron — use **Task Scheduler** to run `python main.py` in this folder
on an hourly trigger.

## More endpoints
See the full ANDX API at [docs.andx.one](https://docs.andx.one).

