"""Read-only preflight: reports instrument availability, pricing, order limits and balances."""

import calendar
import sys
import time

from exchange import Vako
from main import COINS, FEE, SPEND, TP, TP_MARGIN

ROW = "{:<10}{:>13}{:>7}{:>8}{:>8}{:>8}   {}"
HEADER = ROW.format("coin", "price", "age", "taker", "spread", "cost", "verdict")


def age_of(ts):
    """Return how long ago a price was stamped. Accepts UTC strings or epochs; never raises."""
    if ts is None:
        return "no ts"
    try:
        stamp = float(ts)
        stamp = stamp / 1000 if stamp > 1e11 else stamp
    except (TypeError, ValueError):
        text = str(ts).replace("T", " ").replace("Z", "").split(".")[0]
        try:
            stamp = calendar.timegm(time.strptime(text, "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            return str(ts)[:8]
    secs = time.time() - stamp
    age = f"{secs:.0f}s" if abs(secs) < 90 else f"{secs / 60:.0f}m"
    return age


def login():
    vako = Vako()
    vako.login()
    print("login OK\n")
    return vako


def read_fees(vako):
    """Return {instrument: taker fee}, or {} if the endpoint fails."""
    try:
        fees = vako.fees()
    except Exception as exc:
        print(f"trading_fees failed ({exc}) — falling back to FEE={FEE} for every coin\n")
        return {}
    if not fees:
        print(f"trading_fees returned nothing — falling back to FEE={FEE} for every coin\n")
    return fees


def coin_row(vako, coin, fees):
    """Build one table row; `cost` is the round trip of both fees plus the spread."""
    try:
        book = vako.book(coin)
        bid, ask = float(book["bid"]), float(book["ask"])
        price = (bid + ask) / 2
    except Exception as exc:
        row = ROW.format(coin, "--", "--", "--", "--", "--", f"UNAVAILABLE: {exc}")
        return row
    age = age_of(book.get("ts"))
    spread = (ask - bid) / price if price else 0.0
    taker = fees.get(coin)
    if taker is None:
        row = ROW.format(coin, f"{price:.4f}", age, "?", f"{spread*100:.2f}%", "?",
                         f"no fee listed — assuming FEE={FEE}")
        return row
    cost = taker * 2 + spread
    target = max(TP, taker * 2 + TP_MARGIN)
    net = target - cost
    verdict = (f"target +{target*100:.2f}% -> {net*100:+.2f}% net" if net > 0
               else f"target +{target*100:.2f}% LOSES {-net*100:.2f}% (spread eats it)")
    row = ROW.format(coin, f"{price:.4f}", age, f"{taker*100:.2f}%",
                     f"{spread*100:.2f}%", f"{cost*100:.2f}%", verdict)
    return row


def check_balance(vako):
    """Report free USDT against the configured trade size."""
    try:
        usdt = vako.balance("USDT")
    except Exception as exc:
        print(f"\nbalances FAILED ({exc})")
        print("  -> fix the BALANCES query in vako_client.py; until then the bot will never buy in live mode")
        return
    room = "enough" if usdt >= SPEND else "NOT ENOUGH — no buys until topped up"
    print(f"\nfree USDT: {usdt:.2f} (trade size {SPEND:.2f}) — {room}")


def suggest_fee(fees):
    """Suggest the FEE value for .env, averaged over the traded coins."""
    real = [fees[c] for c in COINS if fees.get(c)]
    if not real:
        return
    avg = sum(real) / len(real)
    if abs(avg - FEE) < 0.0001:
        print(f"\nFEE={FEE} already matches the venue's average rate.")
        return
    print(f"\nSet FEE={avg:.4f} in .env so paper mode charges the real rate (currently {FEE}).")


def check_minimums(vako):
    """Report order minimums and decimals for each coin."""
    try:
        specs = {c: vako.specs(c) for c in COINS}
    except Exception as exc:
        print(f"\ninstruments failed ({exc}) — cannot check order minimums")
        return
    print()
    for coin, s in specs.items():
        warn = "  <-- MIN ABOVE TRADE SIZE, buys will fail" if s["min_quote"] > SPEND else ""
        print(f"{coin:<10} min {s['min_quote']:g} USDT / {s['min_base']:g} coin"
              f" | decimals {s['quote_dp']} quote, {s['base_dp']} base{warn}")


def main():
    vako = login()
    fees = read_fees(vako)
    print(HEADER)
    for coin in COINS:
        print(coin_row(vako, coin, fees))
    check_minimums(vako)
    check_balance(vako)
    suggest_fee(fees)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        sys.exit(1)
