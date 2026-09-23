## ⭐ Start here: competition-bot

The main bot for the ANDX trading competition. Use this one if you are entering. It runs a local dashboard
where you paste your API key, pick a strategy and set risk limits. No coding is needed.

→ [competition-bot/](competition-bot/): install and run steps are in its README.

## Other samples

Smaller single-purpose examples for developers.

| Folder | What it does |
|---|---|
| `sample-1` | Order-placement check: log in, place one market order, and confirm the fill. Verifies your API key works end to end. One file. |
| `sample-2` | A strategy bot: trend entries ranked by ADX with take-profit, ATR stop and loss limits, remembers its positions between runs, and can be scheduled. |
| `sample-3` | The same as sample-1, for derivatives: places one margin order, long or short, and reports the position. |

## Getting started

**competition-bot:** follow [competition-bot/README.md](competition-bot/README.md). Run the installer
(`install.sh` on Mac/Linux, `install.ps1` on Windows), then launch `Start Bot`, and enter your keys on the dashboard.

**sample-1 / 2 / 3:** each folder has its own `README.md`, `requirements.txt` and `.env.example`:

    cd sample-1                 # or sample-2, sample-3
    pip install -r requirements.txt
    cp .env.example .env        # then fill in your ANDX credentials
    python main.py

API keys are created from the exchange dashboard under Settings → API Keys.

`sample-1` and `sample-3` place a real order on every run, so test with small amounts. `sample-2` runs in
paper mode by default (`DRY_RUN=1`) and places nothing until you set `DRY_RUN=0`.

