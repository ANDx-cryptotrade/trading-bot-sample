"""volume_bot1 
"""

import hashlib
import hmac
import json
import logging
import os
import sys
import time

import pandas as pd
import requests
import ta

_HERE = os.path.dirname(os.path.abspath(__file__))
log = logging.getLogger("volume_bot1")


# ================= CONFIG (edit here — no separate file) =================

CONFIG = {
    "dry_run": True,
    "initial_cash": 35,
    "quote": "USDT",
    "coins": ["XRP", "UNI", "LINK", "DOGE", "ADA"],
    "max_concurrent": 2,
    "invested_fraction": 1.0,
    "min_order_usd": 5,
    "tp_atr_mult": 2.5,
    "sl_atr_mult": 1.5,
    "tp_floor": 0.008,
    "sl_floor": 0.010,
    "atr_len": 14,
    "rsi_len": 14,
    "trend_ema": 48,
    "loss_budget_pct": 0.30,
    "max_hold_min": 90,
    "daily_loss_halt_pct": 0.15,
}


# ---------------- ANDX client  ----------------

class APIError(Exception):
    pass


class ANDXClient:
    BASE = "https://platform.andx.one"

    def __init__(self, user, token, key="", secret="", passphrase="", timeout=15):
        self.user, self.token = user, token
        self.key, self.secret, self.passphrase = key, secret, passphrase
        self.timeout = timeout
        self.session = requests.Session()

    @classmethod
    def from_env(cls):
        client = cls(user=os.environ.get("ANDX_USER_NAME", ""), token=os.environ.get("ANDX_TOKEN", ""),
                     key=os.environ.get("ANDX_API_KEY", ""), secret=os.environ.get("ANDX_API_SECRET", ""),
                     passphrase=os.environ.get("ANDX_PASSPHRASE", ""))
        return client

    def _post(self, path, payload):
        body = json.dumps(payload)
        ts = str(int(time.time() * 1000))
        sign = hmac.new(self.token.encode(), (self.user + ts + body).encode(), hashlib.sha256).hexdigest().upper()
        headers = {"access-user": self.user, "access-timestamp": ts, "access-sign": sign,
                   "Content-Type": "application/json"}
        r = self.session.post(self.BASE + path, data=body, headers=headers, timeout=self.timeout)
        if r.status_code == 401:
            raise APIError("ANDX token expired (401)")
        r.raise_for_status()
        result = r.json()
        if result.get("status") != "success":
            raise APIError(f"{path} -> {result.get('reason')}")
        data = result["data"]
        return data

    def get_quote(self, buy_code, sell_code, sell_amount):
        quote = self._post("/p/v1/order/get_depth_limits_and_amounts/",
                           {"buy_currency_code": buy_code, "sell_currency_code": sell_code,
                            "sell_currency_amount": sell_amount})
        return quote

    def place_instant_order(self, buy_code, sell_code, sell_amount, buy_amount, visible_price):
        order = self._post("/p/v1/order/instant_order/",
                          {"buy_currency_code": buy_code, "sell_currency_code": sell_code,
                           "sell_amount": sell_amount, "buy_amount": buy_amount,
                           "visible_price": visible_price, "depth_order": True,
                           "with_bonus": False, "with_stake": False})
        return order

    def _get(self, path):
        ts = str(time.time())
        msg = self.key + self.user + self.passphrase + ts + "{}"
        sign = hmac.new(self.secret.encode(), msg.encode(), hashlib.sha256).hexdigest().upper()
        headers = {"ACCESS-KEY": self.key, "ACCESS-USER": self.user, "ACCESS-PASSPHRASE": self.passphrase,
                   "ACCESS-TIMESTAMP": ts, "ACCESS-SIGN": sign, "content-type": "application/json"}
        r = self.session.get(self.BASE + path, headers=headers, timeout=self.timeout)
        if r.status_code == 401:
            raise APIError("ANDX api key rejected (401)")
        r.raise_for_status()
        result = r.json()
        if result.get("status") != "success":
            raise APIError(f"{path} -> {result.get('reason')}")
        data = result["data"]
        return data

    def get_order_status(self, order_number):
        data = self._get(f"/api/v1/order_status/{order_number}/")
        status = data["order"]["status"]
        return status

    def get_available(self, currency, account="Main"):
        """Spendable balance (float) for one currency (key-auth /api/v1/balance/)."""
        data = self._get(f"/api/v1/balance/{account}/")
        entry = data["balances"].get(currency, {})
        available = float(entry.get("available_balance") or 0)
        return available


# ---------------- Coinbase signals via `ta` (ATR / RSI / EMA-trend) — sizing & selection only, never a price ----------------

_CB_BASE = "https://api.exchange.coinbase.com"


def coinbase_indicators(coin, atr_len=14, rsi_len=14, trend_ema=0):
    """From Coinbase 1h candles, standard `ta` indicators: (ATR as a fraction of price, RSI, uptrend bool).
    Coinbase is NEVER used for a price or an order. Returns (None, None, True) if unavailable (trend defaults True
    so a missing signal doesn't block trading)."""
    r = requests.get(f"{_CB_BASE}/products/{coin}-USD/candles", params={"granularity": 3600}, timeout=15)
    r.raise_for_status()
    rows = r.json()                                                # newest-first: [time, low, high, open, close, vol]
    if not rows or len(rows) < max(atr_len, rsi_len, trend_ema) + 3:
        return (None, None, True)
    rows = sorted(rows, key=lambda c: c[0])[:-1]                  # oldest-first; drop the still-forming last bar
    high = pd.Series([c[2] for c in rows], dtype=float)
    low = pd.Series([c[1] for c in rows], dtype=float)
    close = pd.Series([c[4] for c in rows], dtype=float)
    last = float(close.iloc[-1])
    atr = ta.volatility.AverageTrueRange(high, low, close, window=atr_len).average_true_range().iloc[-1]
    rsi = ta.momentum.RSIIndicator(close, window=rsi_len).rsi().iloc[-1]
    atr_frac = float(atr) / last if last and not pd.isna(atr) else None
    rsi = None if pd.isna(rsi) else float(rsi)
    if trend_ema:
        ema = ta.trend.EMAIndicator(close, window=trend_ema).ema_indicator().iloc[-1]
        uptrend = True if pd.isna(ema) else bool(last > float(ema))
    else:
        uptrend = True
    out = (atr_frac, rsi, uptrend)
    return out


# ---------------- config + state ----------------

def load_cfg():
    cfg = dict(CONFIG)                                            # inline config (see CONFIG at top of file)
    env_cash = os.environ.get("INITIAL_CASH")
    if env_cash is not None:
        cfg["initial_cash"] = float(env_cash)
    return cfg


def resolve_dry_run(cfg):
    env = os.environ.get("DRY_RUN")
    if env is not None:
        dry = env not in ("0", "false", "False")
        return dry
    dry = bool(cfg.get("dry_run", True))
    return dry


def load_state(path, initial_cash):
    if os.path.exists(path):
        with open(path) as f:
            st = json.load(f)
        st.setdefault("start_equity", None)
        return st
    st = {"cash": float(initial_cash), "positions": {}, "start_equity": None,
          "day_key": None, "day_start_equity": float(initial_cash),
          "daily_volume": 0.0, "total_volume": 0.0, "realized_pnl": 0.0}
    return st


# ---------------- one trade (quote, then place unless dry-run) ----------------

def do_trade(client, dry_run, buy_code, sell_code, sell_amount):
    """Quote sell_code->buy_code; place the order unless dry-run. Returns (buy_amount, price)."""
    q = client.get_quote(buy_code, sell_code, f"{sell_amount}")
    buy_amount, price = q["buy_currency_amount"], q["visible_price"]
    if not dry_run:
        order = client.place_instant_order(buy_code, sell_code, f"{sell_amount}", buy_amount, price)
        num = order.get("order_number")
        if num:                                                  # short poll for the fill (instant orders settle fast)
            deadline = time.time() + 30
            status = client.get_order_status(num)
            while status not in ("F", "C", "R") and time.time() < deadline:
                time.sleep(2)
                status = client.get_order_status(num)
    out = (float(buy_amount), float(price))
    return out



# ---------------- one cycle ----------------

def run_cycle(cfg, dry_run, client):
    quote_ccy, coins = cfg["quote"], cfg["coins"]
    max_hold_min, max_conc = cfg["max_hold_min"], cfg["max_concurrent"]
    inv_frac, min_order = cfg["invested_fraction"], cfg["min_order_usd"]
    daily_halt, loss_budget_pct = cfg["daily_loss_halt_pct"], cfg.get("loss_budget_pct", 0.0)
    tp_atr_mult, sl_atr_mult = cfg["tp_atr_mult"], cfg["sl_atr_mult"]
    tp_floor, sl_floor = cfg["tp_floor"], cfg["sl_floor"]
    atr_len, rsi_len, trend_ema = cfg["atr_len"], cfg["rsi_len"], cfg["trend_ema"]
    state_path = os.path.join(_HERE, f"scalp_volume_state_{'paper' if dry_run else 'live'}.json")

    st = load_state(state_path, cfg["initial_cash"])
    positions = st["positions"]
    now = time.time()

    cb = {}                                                     # per-cycle cache of Coinbase (ATR%, RSI, uptrend)

    def sig(coin):
        if coin not in cb:
            try:
                cb[coin] = coinbase_indicators(coin, atr_len, rsi_len, trend_ema)
            except Exception as exc:
                log.warning(f"{coin}: coinbase fetch failed ({exc})")
                cb[coin] = (None, None, True)
        return cb[coin]

    def vol_frac(coin, mult, floor):
        frac = sig(coin)[0]                                     # ATR% (Coinbase); floor keeps the stop above the fee
        dist = max(mult * frac, floor) if frac else floor
        return dist

    # 1. EXITS — sell any held coin whose fresh sell-quote clears its take-profit, hits its stop, or is timed out
    held_value = {}
    for coin in list(positions):
        pos = positions[coin]
        units = pos["units"]
        if not dry_run:
            try:
                avail = client.get_available(coin)
                units = min(units, avail) if avail > 0 else 0     # cap at what we hold; 0 = not visible yet (lag/hiccup)
            except Exception:
                pass                                              # fetch failed -> fall back to tracked units
        if units <= 0:
            held_value[coin] = pos["basis"]                       # DON'T forget it on a transient 0 read — keep & retry next cycle
            log.warning(f"{coin}: 0 sellable right now — keeping position, will retry")
            continue
        try:
            proceeds, price = do_trade(client, True, quote_ccy, coin, units)   # read-only sell-quote
        except Exception as exc:
            log.warning(f"{coin}: sell-quote failed ({exc})")
            continue
        basis, age_min = pos["basis"], (now - pos["entry_ts"]) / 60.0
        take = proceeds >= basis * (1 + pos["tp_frac"])
        stop = proceeds <= basis * (1 - pos["sl_frac"])
        timed = age_min >= max_hold_min
        if take or stop or timed:
            if not dry_run:
                try:
                    do_trade(client, False, quote_ccy, coin, units)            # place the real sell
                except Exception as exc:
                    log.error(f"{coin}: SELL failed ({exc})")
                    held_value[coin] = proceeds
                    continue
            reason = "take" if take else ("stop" if stop else "time")
            pnl = proceeds - basis
            st["cash"] += proceeds
            st["daily_volume"] += proceeds
            st["total_volume"] += proceeds
            st["realized_pnl"] += pnl
            positions.pop(coin)
            log.info(f"SELL {coin} +${proceeds:.2f} ({reason}, pnl {pnl:+.2f}, held {age_min:.0f}m) "
                     f"| cum_vol=${st['total_volume']:,.0f}")
        else:
            held_value[coin] = proceeds

    # cash for THIS cycle: LIVE reads the REAL ANDX USDT balance; PAPER uses tracked sim cash
    if dry_run:
        cash = st["cash"]
    else:
        try:
            cash = client.get_available(quote_ccy)
        except Exception as exc:
            log.warning(f"balance fetch failed ({exc}); using tracked cash")
            cash = st["cash"]

    # 2. equity, loss budget, day rollover, daily-loss halt
    equity = cash + sum(held_value.get(c, positions[c]["basis"]) for c in positions)   # just-bought valued at cost
    if st.get("start_equity") is None:
        st["start_equity"] = equity                            # anchor the $ loss cap to where we started
    total_loss = st["start_equity"] - equity
    loss_pct = total_loss / st["start_equity"] if st["start_equity"] else 0.0
    budget_hit = loss_budget_pct and loss_pct >= loss_budget_pct
    day_key = time.strftime("%Y-%m-%d", time.gmtime(now))
    if st["day_key"] != day_key:
        st["day_key"], st["day_start_equity"], st["daily_volume"] = day_key, equity, 0.0
    day_ret = (equity - st["day_start_equity"]) / st["day_start_equity"] if st["day_start_equity"] else 0.0
    block_buys = budget_hit or day_ret <= -daily_halt
    if budget_hit:
        log.info(f"LOSS BUDGET reached (down {loss_pct*100:.1f}% / ${total_loss:.2f} >= {loss_budget_pct*100:.0f}%) "
                 f"— buys stopped, holding cash")

    # 3. ENTRIES — open up to `free` new positions among eligible coins not already held
    free = max_conc - len(positions)
    if free > 0 and not block_buys:
        cand = []
        for c in coins:
            if c in positions:
                continue
            atr, rsi, up = sig(c)
            if not atr or rsi is None:
                continue
            if trend_ema and not up:
                continue
            cand.append((c, rsi))
        cand.sort(key=lambda x: x[1])
        picks = ([cand[0][0]] if cand else []) + ([cand[-1][0]] if len(cand) > 1 else [])
        picks = picks[:free]
        per_slot = equity * inv_frac / max_conc
        for coin in picks:
            spend = min(per_slot, cash / 1.02)                 # ~2% cushion; capped by the REAL available balance
            if spend < min_order:
                break
            tp_frac = vol_frac(coin, tp_atr_mult, tp_floor)
            sl_frac = vol_frac(coin, sl_atr_mult, sl_floor)
            try:
                units, price = do_trade(client, dry_run, coin, quote_ccy, round(spend, 4))
            except Exception as exc:
                log.warning(f"{coin}: BUY failed ({exc})")
                continue
            positions[coin] = {"units": units, "basis": spend, "entry_ts": now, "entry_price": price,
                               "tp_frac": tp_frac, "sl_frac": sl_frac}
            cash -= spend
            st["daily_volume"] += spend
            st["total_volume"] += spend
            log.info(f"BUY  {coin} -${spend:.2f} @ {price:.6f} "
                     f"(target +{tp_frac*100:.2f}% / stop -{sl_frac*100:.2f}%) | cum_vol=${st['total_volume']:,.0f}")

    # 4. persist + log
    st["cash"] = cash
    equity = cash + sum(held_value.get(c, positions[c]["basis"]) for c in positions)
    with open(state_path, "w") as f:
        json.dump(st, f, indent=2)
    log.info(f"cycle end | mode={'PAPER' if dry_run else 'LIVE'} | equity={equity:.2f} | cash={st['cash']:.2f} "
             f"| held={list(positions)} | cum_vol=${st['total_volume']:,.0f} "
             f"| realized_pnl={st['realized_pnl']:+.2f}{' | BUYS HALTED' if block_buys else ''}")
    return st


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_cfg()
    dry_run = resolve_dry_run(cfg)
    client = ANDXClient.from_env()
    if not client.user or not client.token:                      # friendly nudge — every trade needs these
        log.warning("ANDX_USER_NAME / ANDX_TOKEN not set — did you run `. ./.env` first? Trades will fail without them.")
    if not dry_run and not (client.key and client.secret and client.passphrase):
        log.warning("LIVE mode but ANDX_API_KEY/SECRET/PASSPHRASE missing — balance & fill checks will fail.")
    loop_secs = None
    if "--loop" in sys.argv:
        i = sys.argv.index("--loop")
        loop_secs = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) else 900
    if loop_secs:
        log.info(f"looping every {loop_secs}s ({'PAPER' if dry_run else 'LIVE'}) — Ctrl-C to stop")
        while True:
            try:
                run_cycle(cfg, dry_run, client)
            except Exception as exc:
                log.error(f"cycle error: {exc}")
            time.sleep(loop_secs)
    else:
        run_cycle(cfg, dry_run, client)


if __name__ == "__main__":
    main()

