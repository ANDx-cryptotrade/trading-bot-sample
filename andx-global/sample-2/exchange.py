"""Vako interprets the API responses; Store holds positions, daily P&L and the logs."""

import json
import math
import os
import time

import vako_client as api

HERE = os.path.dirname(os.path.abspath(__file__))


class Vako:
    """Exchange access. Logs in once and reuses the token."""

    def __init__(self):
        self.token = None
        self._specs = None                

    def login(self):
        self.token = api.get_jwt()
        return self.token

    def book(self, instrument):
        """Return the raw top of book for one instrument."""
        top = api.get_price(instrument, self.token)
        return top

    def price(self, instrument):
        """Return the mid price between bid and ask."""
        book = self.book(instrument)
        bid, ask = book.get("bid"), book.get("ask")
        if not bid or not ask:
            raise RuntimeError(f"{instrument} has no bid/ask right now (bid={bid} ask={ask})")
        mid = (float(bid) + float(ask)) / 2
        return mid

    def bars(self, instrument, limit=200, periodicity="hour"):
        """Return raw OHLC candles."""
        candles = api.get_bars(instrument, self.token, limit, periodicity)
        return candles

    def fees(self):
        """Return {instrument_id: taker fee}; the rate may sit in taker_flat or taker_progressive."""
        out = {}
        for row in api.get_trading_fees(self.token):
            taker = max(float(row["taker_flat"] or 0), float(row["taker_progressive"] or 0))
            if row["instrument_id"] and taker:
                out[row["instrument_id"]] = taker
        return out

    def balance(self, currency):
        """Return the spendable balance for one currency."""
        rows = api.get_balances(self.token)
        row = next((a for a in rows if a["currency_id"] == currency), None)
        free = float(row["free_balance"] or 0) if row else 0.0
        return free

    def specs(self, instrument):
        """Return decimals and order minimums for one instrument, fetched once per run."""
        if self._specs is None:
            self._specs = {}
            for row in api.get_instruments(self.token):
                base = row.get("quantity_decimals")
                if base is None:
                    base = (row.get("base_currency") or {}).get("precision") or 8
                self._specs[row["instrument_id"]] = {
                    "base_dp": int(base),
                    "quote_dp": int((row.get("quote_currency") or {}).get("precision") or 2),
                    "min_base": float(row.get("min_quantity") or 0),
                    "min_quote": float(row.get("min_quote_quantity") or 0),
                }
        spec = self._specs.get(instrument, {"base_dp": 8, "quote_dp": 2, "min_base": 0, "min_quote": 0})
        return spec

    def fit(self, instrument, quantity, mode):
        """Round a quantity down to the venue's decimals and reject sub-minimum sizes."""
        spec = self.specs(instrument)
        digits = spec["quote_dp"] if mode == "quote" else spec["base_dp"]
        floor = spec["min_quote"] if mode == "quote" else spec["min_base"]
        step = 10 ** digits
        fitted = math.floor(float(quantity) * step) / step
        if fitted <= 0:
            raise RuntimeError(f"{instrument} {mode} quantity {quantity} rounds to 0 at {digits} decimals")
        if floor and fitted < floor:
            raise RuntimeError(f"{instrument} {mode} quantity {fitted} below venue minimum {floor}")
        return fitted

    def buy(self, instrument, usdt):
        """Buy with the given USDT amount. Returns (units, spent, price)."""
        filled = self._order(instrument, "buy", usdt, "quote")
        return filled

    def sell(self, instrument, units):
        """Sell up to this many coins, capped at the balance held. Returns (units, proceeds, price)."""
        base = instrument[:-4] if instrument.endswith("USDT") else instrument
        try:
            held = self.balance(base)
        except Exception:
            held = 0.0
        if held:
            units = min(units, held)
        filled = self._order(instrument, "sell", units, "base")
        return filled

    def _order(self, instrument, side, quantity, mode):
        quantity = self.fit(instrument, quantity, mode)
        placed = api.create_order(instrument, side, quantity, mode, self.token)
        done = self._wait_for_fill(instrument, placed["order_id"])
        price = float(done["price"] or 0)
        executed = float(done["executed_quantity"] or 0)
        if not executed or not price:
            raise RuntimeError(f"{instrument} {side} not filled "
                               f"(status={done['status']}, {done.get('message')})")
        units = executed / price if done["quantity_mode"] == "quote" else executed
        usdt = executed if done["quantity_mode"] == "quote" else executed * price
        out = (units, usdt, price)
        return out

    def _wait_for_fill(self, instrument, order_id, seconds=30):
        """Poll closed_orders until the order settles."""
        deadline = time.time() + seconds
        while time.time() < deadline:
            time.sleep(2)
            for row in api.get_closed_orders(self.token, instrument):
                if row["order_id"] == order_id:
                    return row
        raise RuntimeError(f"{instrument} order {order_id} did not settle in {seconds}s "
                           f"— CHECK IT MANUALLY before rerunning")


class Store:
    """Persisted state: open positions, daily P&L and trade logs."""

    def __init__(self, mode):
        self.mode = mode
        self.path = os.path.join(HERE, f"state_{mode}.json")
        if os.path.exists(self.path):
            with open(self.path) as f:
                self.data = json.load(f)
        else:
            self.data = {"positions": {}, "trades": 0, "pnl": 0.0,
                         "day": "", "day_pnl": 0.0, "day_trades": 0}
        self._roll_day()

    def _roll_day(self):
        """Reset the daily counters on a new UTC day."""
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if self.data["day"] != today:
            self.data["day"], self.data["day_pnl"], self.data["day_trades"] = today, 0.0, 0
        self.data.setdefault("day_trades", 0)

    @property
    def positions(self):
        return self.data["positions"]

    def open_position(self, coin, units, spent, price, tp, sl):
        """Record a new position with its take-profit and stop levels."""
        self.data["positions"][coin] = {"units": units, "spent": spent, "entry": price,
                                        "at": time.time(), "tp": tp, "sl": sl}

    def close_position(self, coin, proceeds):
        pnl = proceeds - self.data["positions"][coin]["spent"]
        del self.data["positions"][coin]
        self.data["trades"] += 1
        self.data["pnl"] += pnl
        self.data["day_pnl"] += pnl
        self.data["day_trades"] += 1
        return pnl

    def invested(self):
        total = sum(p["spent"] for p in self.data["positions"].values())
        return total

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def say(self, msg):
        """Write one timestamped line to stdout and run.log."""
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        with open(os.path.join(HERE, "run.log"), "a") as f:
            f.write(line + "\n")

    def log_trade(self, coin, action, price, usdt, reason, pnl=""):
        cols = ["time", "coin", "action", "price", "usdt", "pnl", "reason"]
        path = os.path.join(HERE, f"trades_{self.mode}.csv")
        new = not os.path.exists(path)
        with open(path, "a") as f:
            if new:
                f.write(",".join(cols) + "\n")
            f.write(f"{time.strftime('%F %T')},{coin},{action},{price:.4f},{usdt:.2f},{pnl},{reason}\n")
