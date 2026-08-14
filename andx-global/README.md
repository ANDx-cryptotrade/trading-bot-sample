# trading-bot-samples

Sample trading bots for the ANDX Global exchange. Each sample is self-contained in its own folder — pick one,
copy it, and build from there.

## Samples

| Folder | What it does |
|---|---|
| `sample-1` | Order-placement check: log in, place one market order, and confirm the fill — verifies your API key works end to end. One file. Start here. |
| `sample-2` | A strategy bot: trend entries ranked by ADX with take-profit, ATR stop and loss limits, remembers its positions between runs, and can be scheduled. |

## Getting started

Each folder has its own `README.md`, `requirements.txt` and `.env.example`. In short:

    cd sample-1                 # or sample-2
    pip install -r requirements.txt
    cp .env.example .env        # then fill in your ANDX credentials
    python main.py

API keys are created from the exchange dashboard under Settings → API Keys.

`sample-1` places a real order on every run, so test with small amounts. `sample-2` runs in paper mode by
default (`DRY_RUN=1`) and places nothing until you set `DRY_RUN=0`.

## Scheduling

The samples perform one cycle per run; a scheduler repeats them. On Linux and macOS use cron, on Windows use
Task Scheduler — see `sample-2/README.md` for both.

## More endpoints

These samples use only part of the ANDX API. For the full reference, see https://docs.andxus.io

## Disclaimer

These samples are provided as an educational reference. Automated trading carries risk of financial loss.
Test with small amounts before deploying against live funds, and use at your own risk.
