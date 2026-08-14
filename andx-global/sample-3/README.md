# sample-3 — derivatives order placement

Authenticates, places a single margin market order, and reports the resulting position. The derivatives
counterpart to sample-1, contained in one file.

## Setup

    pip install -r requirements.txt
    cp .env.example .env        # add ANDX_API_KEY and ANDX_API_SECRET

The API key must be created with the Derivatives permissions enabled.

## Usage

    python main.py

Order parameters are defined in `.env`:

| Variable | Description |
|---|---|
| `INSTRUMENT` | The contract, for example `BTCUSDT` |
| `SIDE` | `buy` opens a long position, `sell` opens a short position |
| `QUANTITY` | Size, expressed in the base currency |
| `LEVERAGE` | Within the contract's minimum and maximum |

## Notes

The derivatives service is hosted on a separate root domain, configured through `ANDX_MARGIN_URL`.
Authentication remains on the main exchange, and the resulting token is accepted by both services.

Before placing the order the script calls `estimate_margin_user_position`, which reports the margin a position
would require without committing to it. Including this check in your own implementation avoids orders being
rejected for insufficient margin.

A position is closed by submitting the opposite side with the same quantity and leverage. Leverage cannot be
modified while a position remains open.

Each run places a live order.

API reference: https://docs.andxus.io
