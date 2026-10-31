"""OHLC bars: load from CSV (MT5 / NinjaTrader exports or plain), Yahoo, or the
MetaTrader5 Python package, cache them, and compute ATR and friends.

A bar is a tuple (t, o, h, l, c, v) where t is the bar's START as UTC epoch seconds.
"""

import csv
import datetime as _dt
import gzip
import io
import json
import os
import re
import urllib.request

from . import store, tz

YAHOO = "https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval={iv}&range={rng}&includePrePost=false"
UA = "Mozilla/5.0 (fx-futures-trader; personal use)"


# ---------------------------------------------------------------- clock helpers for broker files

def _shift_zone(zone):
    """'UTC+3' / 'UTC-5' fixed offsets, or 'NY+7' (US-DST-following broker time,
    the usual MT5 server time: GMT+2 in winter, GMT+3 in summer)."""
    m = re.fullmatch(r"UTC([+-]\d{1,2})(?::?(\d\d))?", zone or "")
    if m:
        sign = -1 if m.group(1).startswith("-") else 1
        mins = int(m.group(1)) * 60 + sign * int(m.group(2) or 0)
        return ("fixed", mins)
    m = re.fullmatch(r"NY([+-]\d{1,2})", zone or "")
    if m:
        return ("ny", int(m.group(1)) * 60)
    return ("zone", zone or "UTC")


def local_to_epoch(naive, zone):
    kind, arg = _shift_zone(zone)
    if kind == "fixed":
        return int((naive - _dt.timedelta(minutes=arg)).replace(tzinfo=tz.UTC).timestamp())
    if kind == "ny":
        return tz.epoch(tz.to_utc(naive - _dt.timedelta(minutes=arg), "America/New_York"))
    return tz.epoch(tz.to_utc(naive, arg))


# ---------------------------------------------------------------- CSV

def _num(x):
    return float(str(x).strip().replace(",", ""))


def parse_csv_text(text, zone="UTC", bar_time="start", tf_min=None):
    """Read MT5 exports (<DATE> <TIME> ...), NinjaTrader exports
    (yyyyMMdd HHmmss;o;h;l;c;v) or a plain CSV with time/open/high/low/close[/volume]."""
    text = text.lstrip("﻿")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    first = lines[0]
    out = []
    if re.match(r"^\d{8} \d{6};", first):                      # NinjaTrader export
        for ln in lines:
            p = ln.split(";")
            naive = _dt.datetime.strptime(p[0], "%Y%m%d %H%M%S")
            out.append([local_to_epoch(naive, zone)] + [_num(x) for x in p[1:5]] + [_num(p[5]) if len(p) > 5 else 0.0])
        if bar_time == "start" and out:
            bar_time = "end"   # NinjaTrader stamps a bar with its close time
    else:
        delim = "\t" if "\t" in first else (";" if first.count(";") > first.count(",") else ",")
        rows = list(csv.reader(lines, delimiter=delim))
        head = [h.strip().strip("<>").lower() for h in rows[0]]
        has_head = any(h in head for h in ("open", "close", "date", "time", "datetime", "timestamp"))
        body = rows[1:] if has_head else rows
        if not has_head:
            head = ["datetime", "open", "high", "low", "close", "volume"][:len(rows[0])]
        idx = {h: i for i, h in enumerate(head)}
        vol_key = next((k for k in ("volume", "vol", "tickvol") if k in idx), None)
        for r in body:
            if not r or not "".join(r).strip():
                continue
            if "date" in idx and "time" in idx:
                stamp = r[idx["date"]].strip() + " " + r[idx["time"]].strip()
            else:
                stamp = r[idx.get("datetime", idx.get("timestamp", idx.get("time", idx.get("date", 0))))].strip()
            if re.fullmatch(r"\d{9,11}", stamp):
                t = int(stamp)
            elif re.fullmatch(r"\d{12,14}", stamp):
                t = int(stamp) // 1000
            else:
                s = stamp.replace(".", "-", 2) if re.match(r"^\d{4}\.\d\d\.\d\d", stamp) else stamp
                s = s.replace("T", " ").replace("Z", "+00:00")
                try:
                    dt = _dt.datetime.fromisoformat(s)
                except ValueError:
                    dt = _dt.datetime.strptime(s, "%Y-%m-%d %H:%M")
                t = int(dt.astimezone(tz.UTC).timestamp()) if dt.tzinfo else local_to_epoch(dt, zone)
            v = _num(r[idx[vol_key]]) if vol_key and r[idx[vol_key]].strip() else 0.0
            out.append([t, _num(r[idx["open"]]), _num(r[idx["high"]]), _num(r[idx["low"]]), _num(r[idx["close"]]), v])
    out.sort(key=lambda b: b[0])
    if bar_time == "end" and len(out) > 1:
        step = int((tf_min or 0) * 60) or min(b[0] - a[0] for a, b in zip(out, out[1:]) if b[0] > a[0])
        out = [[b[0] - step] + b[1:] for b in out]
    return [tuple(b) for b in dedupe(out)]


def dedupe(bars):
    seen, out = set(), []
    for b in bars:
        if b[0] not in seen:
            seen.add(b[0])
            out.append(b)
    return out


# ---------------------------------------------------------------- Yahoo

def yahoo_bars(symbol, tf_min=5, days=60, opener=None):
    iv = {1: "1m", 2: "2m", 5: "5m", 15: "15m", 30: "30m", 60: "60m", 1440: "1d"}[tf_min]
    days = min(days, 7 if tf_min == 1 else 59 if tf_min < 60 else 730)
    url = YAHOO.format(sym=urllib.request.quote(symbol), iv=iv, rng="%dd" % days)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    raw = (opener or urllib.request.urlopen)(req, timeout=30).read()
    return parse_yahoo(json.loads(raw.decode("utf-8")))


def parse_yahoo(doc):
    res = (doc.get("chart") or {}).get("result") or []
    if not res:
        err = (doc.get("chart") or {}).get("error")
        raise ValueError("Yahoo returned no data: %s" % (err,))
    r = res[0]
    ts = r.get("timestamp") or []
    q = r["indicators"]["quote"][0]
    out = []
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        out.append((int(t), float(o), float(h), float(l), float(c), float((q.get("volume") or [0] * len(ts))[i] or 0)))
    return dedupe(out)


# ---------------------------------------------------------------- MetaTrader5 package (Windows)

def mt5_bars(symbol, tf_min=5, count=20000, server_tz="NY+7"):
    try:
        import MetaTrader5 as mt5  # noqa: N813  (pip install MetaTrader5, Windows only)
    except ImportError:
        raise RuntimeError("the MetaTrader5 package is not installed: pip install MetaTrader5 (Windows, MT5 running)")
    if not mt5.initialize():
        raise RuntimeError("MetaTrader5.initialize() failed: is the MT5 terminal open and logged in? %s" % (mt5.last_error(),))
    tfs = {1: mt5.TIMEFRAME_M1, 5: mt5.TIMEFRAME_M5, 15: mt5.TIMEFRAME_M15, 30: mt5.TIMEFRAME_M30, 60: mt5.TIMEFRAME_H1}
    rates = mt5.copy_rates_from_pos(symbol, tfs[tf_min], 0, count)
    if rates is None:
        raise RuntimeError("MT5 has no bars for %s: %s" % (symbol, mt5.last_error()))
    out = []
    for r in rates:
        # MT5 stamps bars in the trade server's clock, written as if it were UTC.
        naive = _dt.datetime(1970, 1, 1) + _dt.timedelta(seconds=int(r["time"]))
        out.append((local_to_epoch(naive, server_tz), float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["tick_volume"])))
    return out


# ---------------------------------------------------------------- cache + one entry point

def cache_path(symbol, tf_min):
    return store.path("bars", "%s-%dm.json" % (symbol, tf_min))


def save_cache(symbol, tf_min, bars):
    old = read_cache(symbol, tf_min)
    merged = {b[0]: b for b in old}
    merged.update({b[0]: tuple(b) for b in bars})
    store.write_json(cache_path(symbol, tf_min), [list(merged[k]) for k in sorted(merged)])


def read_cache(symbol, tf_min):
    p = cache_path(symbol, tf_min)
    if os.path.exists(p):
        return [tuple(b) for b in store.read_json(p, [])]
    if os.path.exists(p + ".gz"):
        with gzip.open(p + ".gz", "rt", encoding="utf-8") as f:
            return [tuple(b) for b in json.load(f)]
    return []


def load(spec, tf_min=5, source="auto", days=60, csv_path=None, config=None, csv_tz=None, offline=False):
    """Bars for one instrument. source: auto | cache | csv | yahoo | mt5.

    auto: CSV if given, else MT5 when the instrument has an MT5 symbol and the
    package works, else Yahoo when the instrument has a Yahoo symbol, else cache.
    Whatever is fetched is merged into trader/bars/ so later runs work offline.
    """
    config = config or store.load_config()
    sym = spec["symbol"]
    if csv_path:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            bars = parse_csv_text(f.read(), zone=csv_tz or spec.get("csv_tz") or config.get("csv_tz") or "UTC", tf_min=tf_min)
        save_cache(sym, tf_min, bars)
        return bars, "csv:" + os.path.basename(csv_path)
    if source == "cache" or offline or os.environ.get("FX_OFFLINE"):
        return read_cache(sym, tf_min), "cache"
    errors = []
    order = [source] if source != "auto" else ["mt5", "yahoo"]
    for src in order:
        try:
            if src == "mt5" and spec.get("brokers", {}).get("mt5"):
                bars = mt5_bars(spec["brokers"]["mt5"], tf_min, server_tz=config["brokers"]["mt5"].get("server_tz", "NY+7"))
            elif src == "yahoo" and spec.get("yahoo"):
                bars = yahoo_bars(spec["yahoo"], tf_min, days)
            else:
                continue
            save_cache(sym, tf_min, bars)
            label = src + (" (proxy %s)" % spec["yahoo"] if src == "yahoo" and spec.get("yahoo_proxy") else "")
            return read_cache(sym, tf_min), label
        except Exception as e:  # fall through to the next source, then the cache
            errors.append("%s: %s" % (src, e))
    cached = read_cache(sym, tf_min)
    if cached:
        return cached, "cache (live failed: %s)" % "; ".join(errors) if errors else "cache"
    raise RuntimeError("no bars for %s. %s Give a CSV export with --csv (MT5: right-click chart > Bars > Export; NinjaTrader: Tools > Historical Data > Export)." % (sym, "; ".join(errors)))


# ---------------------------------------------------------------- maths

def true_ranges(bars):
    out = []
    for i, b in enumerate(bars):
        pc = bars[i - 1][4] if i else b[4]
        out.append(max(b[2] - b[3], abs(b[2] - pc), abs(b[3] - pc)))
    return out


def atr(bars, n=14):
    tr = true_ranges(bars)
    if not tr:
        return None
    if len(tr) < n:
        return sum(tr) / len(tr)
    a = sum(tr[:n]) / n
    for x in tr[n:]:
        a = (a * (n - 1) + x) / n
    return a


def ema(values, n):
    if not values:
        return None
    k = 2.0 / (n + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def local_date(t, zone):
    return tz.to_local(tz.from_epoch(t), zone).date()


def daily(bars, zone):
    """Aggregate to one bar per local calendar day in `zone`."""
    days = {}
    for b in bars:
        d = local_date(b[0], zone)
        if d not in days:
            days[d] = [b[0], b[1], b[2], b[3], b[4], b[5]]
        else:
            x = days[d]
            x[2] = max(x[2], b[2]); x[3] = min(x[3], b[3]); x[4] = b[4]; x[5] += b[5]
    return [tuple(days[d]) for d in sorted(days)], sorted(days)


def tf_of(bars):
    if len(bars) < 2:
        return 5
    gaps = sorted(b[0] - a[0] for a, b in zip(bars, bars[1:]) if b[0] > a[0])
    return max(1, gaps[len(gaps) // 2] // 60)


def gz_json(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def read_text_any(path):
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return f.read()
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()
