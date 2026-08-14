# sample-2 — strategy bot

A reference implementation of an automated spot trading strategy on the ANDX exchange, together with the
GraphQL API client it is built on. Intended as a starting point for developers building their own bots.

## Requirements

Python 3.8 or later.

    pip install -r requirements.txt

An ANDX API key and secret, created from the exchange dashboard under Settings → API Keys.

## Project structure

| File | Purpose |
|---|---|
| `vako_client.py` | GraphQL API client — one function per endpoint |
| `exchange.py` | Interprets API responses and maintains position state |
| `signals.py` | EMA trend, ADX and ATR indicators |
| `main.py` | Strategy and entry point |
| `check.py` | Read-only preflight check |
| `scan.py` | Read-only market scan |

## Strategy

On each run the bot evaluates every configured instrument and opens a position where the price is above its
48-hour EMA, ranking candidates by ADX and allocating the available slots to the strongest trends. Positions
are closed on a take-profit target, an ATR-derived stop, or a maximum hold time.

New entries are suspended when the daily loss limit is reached, when cumulative losses exceed `LOSS_LIMIT`,
when the BTC market gate indicates a downtrend, or when no slot or balance is available. Exit logic always
runs. The daily limit resets at UTC midnight; the cumulative limit does not, and requires manual review of
the recorded state before trading resumes.

## Configuration

Copy the example environment file and add your credentials:

    cp .env.example .env

Default parameters are defined at the top of `main.py` and may be overridden through `.env`. The bot runs in
paper mode (`DRY_RUN=1`) unless explicitly set otherwise.

## Usage

    python check.py             # verify connectivity and instrument limits; places no orders
    python main.py              # single cycle in paper mode
    DRY_RUN=0 python main.py    # single cycle against live funds

To run continuously, schedule the script at a fixed interval.

Linux and macOS, using cron:

    */10 * * * * cd /path/to/bot && /usr/bin/python3 main.py >> bot.log 2>&1

Windows, using Task Scheduler:

    schtasks /create /tn "ANDX Bot" /tr "cmd /c cd /d C:\path\to\bot && python main.py >> bot.log 2>&1" ^
             /sc minute /mo 10 /f

The task can also be created through the Task Scheduler interface: create a basic task, set the trigger to
repeat every 10 minutes indefinitely, set the action to start `python.exe` with `main.py` as the argument,
and set "Start in" to the bot directory. Both schedulers run with a minimal environment, so use absolute
paths and confirm the working directory is the bot folder — the script reads `.env` and writes its state
files relative to its own location.

## Notes

Paper and live modes keep separate files and never share data: state in `state_paper.json` or
`state_live.json`, and a record of every order — one row per entry and per exit — in `trades_paper.csv` or
`trades_live.csv`. Each run also appends to `run.log`.

## Reference

API documentation: https://docs.andxus.io

## Disclaimer

This software is provided as an educational reference. Automated trading carries risk of financial loss. Test
in paper mode before deploying against live funds, and use at your own risk.
