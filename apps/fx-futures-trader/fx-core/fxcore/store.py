"""The trader/ working folder, JSON files, config, the clock and money."""

import copy
import datetime as _dt
import hashlib
import json
import os
import tempfile

from . import tz

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_CONFIG = {
    "account": {
        "ccy": "USD",
        "balance": 10000,
        "risk_per_trade_pct": 0.5,
        "risk_per_trade_money": None
    },
    "display_tz": "Asia/Kolkata",
    "watchlist": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "ES", "NQ", "GC", "CL", "MCX_GOLD", "NIFTY"],
    "paper": True,
    "broker": "signals",
    "brokers": {
        "mt5": {"common_files": None, "folder": "RajeshHub\\tickets", "magic": 20261031, "slippage_points": 30},
        "ninjatrader": {"incoming": None, "outgoing": None, "account": "Sim101", "mode": "protect",
                        "atm_templates": {}, "contract_months": {}}
    },
    "rates": {},
    "plan": {"targets_r": [1, 2, 3], "split": [0.3334, 0.3333, 0.3333], "be_after_tp1": True},
    "limits": {
        "max_risk_pct": 1.0,
        "max_risk_money": None,
        "daily_loss_limit_pct": 2.0,
        "daily_loss_limit_money": None,
        "max_trades_per_day": 3,
        "min_rr": 1.5,
        "max_spread_ticks": None,
        "max_margin_pct": 30,
        "news_blackout_before_min": 15,
        "news_blackout_after_min": 15,
        "news_impacts": ["High"],
        "signal_max_age_min": 10,
        "max_entry_drift_r": 0.25,
        "acknowledge_specs": []
    },
    "approval_valid_min": 10
}


def trader_dir():
    return os.environ.get("FX_TRADER_DIR") or os.path.join(os.getcwd(), "trader")


def path(*parts):
    return os.path.join(trader_dir(), *parts)


def read_json(p, default=None):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return copy.deepcopy(default)


def write_json(p, data):
    """Atomic write: temp file in the same folder, then rename."""
    d = os.path.dirname(os.path.abspath(p))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=False)
            f.write("\n")
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return p


def deep_merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config():
    return deep_merge(DEFAULT_CONFIG, read_json(path("config.json"), {}))


# ---------------------------------------------------------------- the clock

def now_utc(override=None, zone="UTC"):
    """`override` like '2026-10-19 10:15' pins the clock (read in `zone`)."""
    if override:
        return tz.parse_local(override, zone)
    env = os.environ.get("FX_NOW")
    if env:
        return tz.parse_local(env, zone)
    return _dt.datetime.now(tz.UTC).replace(microsecond=0)


def iso(dt):
    return dt.astimezone(tz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text):
    return _dt.datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(tz.UTC)


_ABBR = {"America/New_York": "NY", "Europe/London": "LDN", "Asia/Kolkata": "IST", "Asia/Tokyo": "TYO",
         "America/Chicago": "CHI", "UTC": "UTC"}


def fmt_t(t, zone, with_date=False):
    """Epoch or aware datetime -> 'HH:MM NY' (or 'YYYY-MM-DD HH:MM NY')."""
    if t is None:
        return "-"
    dt = tz.from_epoch(t) if isinstance(t, (int, float)) else t
    loc = tz.to_local(dt, zone)
    return loc.strftime("%Y-%m-%d %H:%M" if with_date else "%H:%M") + " " + _ABBR.get(zone, zone)


def fmt_both(t, market_zone, config, with_date=False):
    disp = config.get("display_tz") or "UTC"
    a = fmt_t(t, market_zone, with_date)
    return a if disp == market_zone else "%s (%s)" % (a, fmt_t(t, disp))


# ---------------------------------------------------------------- money

def convert(amount, src, dst, rates):
    """Convert money with the rates in config (e.g. {"USDINR": 88.2, "USDJPY": 152.1}).

    Looks for SRCDST (multiply) or DSTSRC (divide), then crosses through USD.
    Raises KeyError when no rate is known, so nothing is sized on a guess.
    """
    src, dst = src.upper(), dst.upper()
    if src == dst:
        return amount
    rates = {k.upper(): float(v) for k, v in (rates or {}).items() if v}
    if src + dst in rates:
        return amount * rates[src + dst]
    if dst + src in rates:
        return amount / rates[dst + src]
    if "USD" not in (src, dst):
        return convert(convert(amount, src, "USD", rates), "USD", dst, rates)
    raise KeyError("no exchange rate for %s->%s: add \"%s%s\" to rates in trader/config.json" % (src, dst, src, dst))


def money(amount, ccy):
    sym = {"USD": "$", "INR": "Rs ", "EUR": "EUR ", "GBP": "GBP ", "JPY": "JPY "}.get(ccy.upper(), ccy + " ")
    return "%s%s" % (sym, format(round(amount, 2), ",.2f"))


def fingerprint(obj):
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
