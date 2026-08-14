"""Trend-following spot bot: buys uptrends ranked by ADX, exits on take-profit, stop or timer."""

import os
import sys
import time

import signals
from exchange import Store, Vako

COINS = os.environ.get("COINS", "BTCUSDT,ETHUSDT,XRPUSDT,DOGEUSDT,ADAUSDT").split(",")
MAX_CAPITAL = float(os.environ.get("MAX_CAPITAL", 100))
SLOTS = int(os.environ.get("SLOTS", 3))
SPEND = MAX_CAPITAL / SLOTS
ADX_MIN = float(os.environ.get("ADX_MIN", 25))
REQUIRE_STRONG = os.environ.get("REQUIRE_STRONG", "1") not in ("0", "false", "False")
TP = float(os.environ.get("TP", 0.01))
TP_MARGIN = float(os.environ.get("TP_MARGIN", 0.003))
SL_ATR = float(os.environ.get("SL_ATR", 3.0))
SL_FLOOR = float(os.environ.get("SL_FLOOR", 0.01))
SL_MAX = float(os.environ.get("SL_MAX", 0.02))
MAX_HOLD_MIN = float(os.environ.get("MAX_HOLD_MIN", 180))
DAILY_HALT = float(os.environ.get("DAILY_HALT", 0.015))
LOSS_LIMIT = float(os.environ.get("LOSS_LIMIT", 0.30))
MARKET_GATE = os.environ.get("MARKET_GATE", "1") not in ("0", "false", "False")
FEE = float(os.environ.get("FEE", 0.003))
LIVE = os.environ.get("DRY_RUN", "1") in ("0", "false", "False")


def look(vako, store, coin):
    """Return (bid, ask, uptrend, adx, atr_pct) for one coin, or None if unavailable."""
    try:
        book = vako.book(coin)
        bid, ask = float(book["bid"] or 0), float(book["ask"] or 0)
        uptrend, adx, atr = signals.trend(vako.bars(coin))
    except Exception as exc:
        store.say(f"{coin}: skipped — {exc}")
        return None
    if not bid or not ask:
        store.say(f"{coin}: skipped — no bid/ask (bid={bid} ask={ask})")
        return None
    out = (bid, ask, uptrend, adx, atr)
    return out


def blocked_reason(vako, store):
    """Return the reason buying is blocked this run, or an empty string if allowed."""
    total = LOSS_LIMIT * MAX_CAPITAL
    if store.data["pnl"] <= -total:
        return (f"LOSS LIMIT: down {store.data['pnl']:.2f} USDT overall "
                f"(limit {total:.2f} = {LOSS_LIMIT*100:.0f}% of {MAX_CAPITAL:.0f})")
    limit = DAILY_HALT * MAX_CAPITAL
    if store.data["day_pnl"] <= -limit:
        return (f"DAILY HALT: down {store.data['day_pnl']:.2f} USDT today "
                f"(limit {limit:.2f} = {DAILY_HALT*100:.1f}% of {MAX_CAPITAL:.0f})")
    if len(store.positions) >= SLOTS:
        return f"all {SLOTS} slots full: {list(store.positions)}"
    if MARKET_GATE:
        try:
            if signals.risk_off(vako.bars("BTCUSDT", limit=24)):
                return "BTC GATE: risk-off (below 8h EMA or negative 3h momentum)"
        except Exception as exc:
            store.say(f"    BTC gate failed ({exc}) — gate open")
    if LIVE:
        try:
            free = vako.balance("USDT")
        except Exception as exc:
            store.say(f"    balance check failed ({exc}) — treating as 0")
            free = 0.0
        if free < SPEND:
            return f"only {free:.2f} USDT free, need {SPEND:.2f}"
    return ""


def sell(vako, store, coin, price, head):
    """Exit a position on take-profit, stop or timer. `price` is the bid."""
    pos = store.positions[coin]
    change = price / pos["entry"] - 1
    held = (time.time() - pos["at"]) / 60
    reason = "take-profit" if change >= pos["tp"] else "stop-loss" if change <= -pos["sl"] else \
             "timer" if held >= MAX_HOLD_MIN else None
    if not reason:
        store.say(f"{head} | HOLD: {change*100:+.2f}% vs entry (want {pos['tp']*100:+.2f}% "
                  f"/ stop {-pos['sl']*100:.2f}% / {MAX_HOLD_MIN-held:.0f}m left)")
        return
    store.say(f"{head} | SELL ({reason}): {change*100:+.2f}% vs entry, held {held:.0f}m")
    units = pos["units"]
    units, got, price = vako.sell(coin, units) if LIVE else (units, units * price * (1 - FEE), price)
    pnl = store.close_position(coin, got)
    store.say(f"    SOLD {coin} {units:.8f} @ {price:.4f} for {got:.2f} USDT | pnl {pnl:+.2f}")
    store.log_trade(coin, "SELL", price, got, reason, f"{pnl:+.2f}")


def buy(vako, store, coin, price, adx, atr, fee, spread, head):
    """Open a position at the ask, sizing the stop from ATR. `price` is the ask."""
    tp = max(TP, fee * 2 + TP_MARGIN)
    cost = fee * 2 + spread
    sl = min(max(SL_ATR * atr, SL_FLOOR), SL_MAX)
    tier = "strong" if adx > ADX_MIN else "fallback"
    store.say(f"{head} | BUY ({tier}): ADX {adx:.0f}, target +{tp*100:.2f}% vs entry "
              f"(price must rise {cost*100:.2f}%) / stop -{sl*100:.2f}%")
    units, spent, price = vako.buy(coin, SPEND) if LIVE else (SPEND * (1 - FEE) / price, SPEND, price)
    store.open_position(coin, units, spent, price, tp, sl)
    store.say(f"    BOUGHT {coin} {units:.8f} @ {price:.4f} for {spent:.2f} USDT")
    store.log_trade(coin, "BUY", price, spent, tier)


def run():
    vako = Vako()
    vako.login()
    store = Store("live" if LIVE else "paper")
    try:
        fees = vako.fees()
    except Exception as exc:
        store.say(f"trading_fees failed ({exc}) — using FEE={FEE} for every coin")
        fees = {}

    mode = "LIVE" if LIVE else "PAPER"
    blocked = blocked_reason(vako, store)
    if blocked:
        store.say(f"NO NEW BUYS — {blocked} (exits still run)")

    watch = COINS + [c for c in store.positions if c not in COINS]
    candidates = []
    for coin in watch:
        seen = look(vako, store, coin)
        if not seen:
            continue
        bid, ask, uptrend, adx, atr = seen
        spread = (ask - bid) / ((ask + bid) / 2)
        head = f"[{mode}] {coin} {(ask + bid) / 2:.4f}"
        if coin in store.positions:
            try:
                sell(vako, store, coin, bid, head)
            except Exception as exc:
                store.say(f"{coin}: SELL FAILED ({exc})")
        elif blocked:
            store.say(f"{head} | no buy: blocked this run")
        elif adx is None:
            store.say(f"{head} | no buy: not enough candle history yet")
        elif not uptrend:
            store.say(f"{head} | no buy: below its 48h EMA (downtrend)")
        elif REQUIRE_STRONG and adx <= ADX_MIN:
            store.say(f"{head} | no buy: ADX {adx:.0f} below {ADX_MIN:.0f} (strong-only mode)")
        else:
            candidates.append((coin, ask, adx, atr, spread, head))

    candidates.sort(key=lambda c: -c[2])
    for coin, ask, adx, atr, spread, head in candidates:
        if len(store.positions) >= SLOTS:
            store.say(f"{head} | no buy: slots full (ADX {adx:.0f} ranked too low this run)")
            continue
        try:
            buy(vako, store, coin, ask, adx, atr, fees.get(coin, FEE), spread, head)
        except Exception as exc:
            store.say(f"{coin}: BUY FAILED ({exc})")

    store.say(f"done | held={list(store.positions)} | invested={store.invested():.2f}/{MAX_CAPITAL:.0f} USDT "
              f"| today {store.data['day_trades']} trades {store.data['day_pnl']:+.2f} "
              f"| total {store.data['trades']} trades {store.data['pnl']:+.2f} USDT")
    store.save()


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        sys.exit(1)
