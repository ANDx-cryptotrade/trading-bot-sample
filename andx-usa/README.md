# trading-bot-samples

Sample trading bots for the **ANDX** exchange.
Each sample is self-contained in its own folder — pick one, copy it, and build from there.

## Samples
| Folder | What it does |
|--------|--------------|
| [`sample-1`](sample-1/) | Trade-placement check bot: check the price, place a fixed-amount buy, and confirm the order status — verifies your token + API key work end to end. Three files. Start here. |
| [`sample-2`](sample-2/) | A strategy bot: ema_rsi entries with ATR take-profit / stop-loss, remembers its position between runs, and can be scheduled via cron. |

## Getting started
Each folder has its own `README.md`, `requirements.txt`, and `.env.example`. In short:
```
cd sample-1                 # or sample-2
pip install -r requirements.txt
cp .env.example .env        # then fill in your ANDX credentials
python main.py
```

To obtain the API keys and token, see **STEP 2** at https://andx.ai/set-up-a-bot.
Every run places **real orders** on ANDX, so test with small amounts.

## Scheduling
The samples place one trade per run; a scheduler repeats them. On Linux/macOS use
cron (see `sample-2/README.md`). On Windows, use **Task Scheduler** to run
`python main.py` in the sample folder on an hourly trigger.

## More endpoints
These samples use only a few ANDX endpoints. For the full API, see the docs at
[docs.andx.one](https://docs.andx.one).

