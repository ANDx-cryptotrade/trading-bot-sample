# sample-3 :  Sample volume based bot

A simple single-file bot for **ANDX**. It buys and sells a few coins every ~15 minutes to generate trading volume. 

## Coins it trades
`XRP, UNI, LINK, DOGE, ADA` 

## When it buys
Each cycle the bot evaluates the coins with a set of technical indicators and opens up to 2 positions
in the ones that qualify.

## When it sells
It sells a position when any of these hits:
- **Take-profit:** price is up ~2.5×ATR
- **Stop-loss:** price is down ~1.5×ATR
- **Timer:** the position is 90 minutes old


## Auto-stop
It stops buying and holds cash once the account is **down 30%** from where it started (your loss cap).

## Setup
```bash
pip3 install -r requirements.txt
cp .env.example .env    # fill in your ANDX credentials
mkdir -p logs
```

## Run
```bash
. ./.env && python3 volume_bot1.py            # paper (no real orders)
. ./.env && DRY_RUN=0 python3 volume_bot1.py  # live (real orders)
```

Cron (every 15 min):
```cron
*/15 * * * * cd /home/you/volume_bot && . ./.env && DRY_RUN=0 python3 volume_bot1.py >> logs/live_$(date +\%Y-\%m-\%d).log 2>&1
```

All settings (coins, brackets, loss budget) are in the `CONFIG` block at the top of `volume_bot1.py`.


