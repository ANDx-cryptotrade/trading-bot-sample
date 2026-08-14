# sample-1 — order placement check

Logs in, places one market order, and reports the fill. A single file, intended to confirm your API key and
secret work before building anything larger.

## Setup

    pip install -r requirements.txt
    cp .env.example .env        # add ANDX_API_KEY and ANDX_API_SECRET

## Usage

    python main.py

Order parameters are set in `.env`:

| Variable | Meaning |
|---|---|
| `INSTRUMENT` | The trading pair, for example `BTCUSDT` |
| `SIDE` | `buy` or `sell` |
| `QUANTITY` | The amount, interpreted according to `MODE` |
| `MODE` | `quote` spends the quote currency (buys), `base` sells a coin count (sells) |

## Notes

A market order returns immediately with status `new` and `executed_quantity` of 0. That is not a failure —
the completed fill appears in `closed_orders` a moment later, which is why the script polls before reporting.

Every run places a real order. Start with the smallest amount the instrument allows.

API reference: https://docs.andxus.io
