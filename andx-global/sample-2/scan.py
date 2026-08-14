"""Read-only scan of every USDT pair, ranked by round-trip cost and hit rate."""

import sys
import time

import vako_client as api
from exchange import Vako
from main import FEE, TP, TP_MARGIN

QUOTE = "USDT"
WANT = int(sys.argv[1]) if len(sys.argv) > 1 else 5
MAX_FEE = 0.005
HOURS = 3
STABLE = ("USDC", "USDT", "USD", "DAI", "TUSD", "FDUSD", "USDA1")


def candidates(vako):
    """Return USDT pairs whose listed taker fee is at or under MAX_FEE."""
    fees = vako.fees()
    out = []
    for row in api.get_instruments(vako.token):
        coin = row["instrument_id"]
        fee = fees.get(coin)
        base = coin[: -len(QUOTE)]
        if base in STABLE:
            continue
        if coin.endswith(QUOTE) and fee is not None and 0 < fee <= MAX_FEE:
            out.append((coin, fee))
    return sorted(out)


def hit_rate(vako, coin, target):
    """Return the share of past HOURS-long windows whose high cleared `target`."""
    try:
        bars = vako.bars(coin, limit=400)
    except Exception:
        return None
    closes = [float(b["close"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    if len(closes) < HOURS + 20:
        return None
    wins = 0
    for i in range(len(closes) - HOURS):
        reach = max(highs[i + 1: i + 1 + HOURS]) / closes[i] - 1
        wins += reach >= target
    rate = wins / (len(closes) - HOURS)
    return rate


def measure(vako, coin, fee):
    """Return (cost, spread, price) for one pair, or None without a live book."""
    try:
        book = vako.book(coin)
        bid, ask = float(book["bid"] or 0), float(book["ask"] or 0)
    except Exception:
        return None
    if not bid or not ask:
        return None
    price = (bid + ask) / 2
    spread = (ask - bid) / price
    out = (fee * 2 + spread, spread, price)
    return out


def main():
    vako = Vako()
    vako.login()
    pairs = candidates(vako)
    print(f"{len(pairs)} {QUOTE} pairs at or under {MAX_FEE*100:.2f}% taker — pricing each...\n")

    rows = []
    for coin, fee in pairs:
        seen = measure(vako, coin, fee)
        if seen:
            rows.append((seen[0], coin, fee, seen[1], seen[2]))
        time.sleep(0.1)
    rows.sort()

    print(f"{'coin':<12}{'price':>13}{'taker':>8}{'spread':>9}{'cost':>8}{'target':>9}{'hit':>7}   verdict")
    scored = []
    for cost, coin, fee, spread, price in rows:
        target = max(TP, cost + TP_MARGIN)
        rate = hit_rate(vako, coin, target)
        if rate is None:
            hit, verdict = "  ?", "no candle history"
        else:
            hit = f"{rate*100:.0f}%"
            verdict = (f"reaches +{target*100:.2f}% in {HOURS}h {rate*100:.0f}% of the time"
                       if rate >= 0.25 else f"almost never reaches +{target*100:.2f}%")
            scored.append((rate, coin, fee))
        print(f"{coin:<12}{price:>13.6f}{fee*100:>7.2f}%{spread*100:>8.2f}%{cost*100:>7.2f}%"
              f"{target*100:>8.2f}%{hit:>7}   {verdict}")
        time.sleep(0.1)

    scored.sort(reverse=True)
    best = scored[:WANT]
    if best:
        print(f"\nBest {len(best)} by hit rate:\n  COINS={','.join(c for _, c, _ in best)}")
        avg = sum(f for _, _, f in best) / len(best)
        print(f"  FEE={avg:.4f}" + ("" if abs(avg - FEE) > 1e-9 else "   (unchanged)"))
        weak = [f"{c} {r*100:.0f}%" for r, c, _ in best if r < 0.25]
        if weak:
            print(f"  WARNING: below 25% and probably not worth trading — {', '.join(weak)}")
    else:
        print("\nNothing tradable found.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        sys.exit(1)
