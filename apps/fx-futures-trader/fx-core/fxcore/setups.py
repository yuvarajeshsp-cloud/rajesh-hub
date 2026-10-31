"""The setup rules, shared by the scanner, the entry/exit planner and the time machine.

A *range* is a window of the day (Asian session, London open, the first 15
minutes of the US cash open, MCX 09:00...). Two setups read it:

  break  the first CLOSED bar that closes beyond the range: above the high is a
         long, below the low is a short.
  sweep  a closed bar that trades through the range high or low and closes back
         inside it (a liquidity sweep / stop run): through the low and back
         above is a long, through the high and back below is a short.

Both stay valid only until the range's `until` time.
"""

import datetime as _dt

from . import bars as B
from . import tz

SETUPS = ("break", "sweep")


def window(spec, range_name, day):
    """UTC epochs for one local day: range start/end, until, and the session end."""
    ranges = spec.get("ranges") or {}
    name = range_name or spec.get("default_range") or next(iter(ranges), None)
    if name not in ranges:
        raise KeyError("%s has no range %r (has: %s)" % (spec["symbol"], range_name, ", ".join(ranges)))
    r = ranges[name]
    z = r["tz"]

    def at(hhmm, d=day):
        return tz.epoch(tz.to_utc(_dt.datetime.combine(d, tz.hhmm(hhmm)), z))

    start, end, until = at(r["start"]), at(r["end"]), at(r["until"])
    if end <= start:
        end += 86400
    while until <= end:
        until += 86400
    sess = spec.get("session") or {}
    flat = None
    if sess.get("flat_by"):
        sz = sess.get("tz", z)
        local_day = tz.to_local(tz.from_epoch(start), sz).date()
        flat = tz.epoch(tz.to_utc(_dt.datetime.combine(local_day, tz.hhmm(sess["flat_by"])), sz))
        if flat <= until:
            flat += 86400
    horizon = flat or (until + int(r.get("hold_hours", 8) * 3600))
    return {"range": name, "tz": z, "start": start, "end": end, "until": until, "flat_by": flat, "horizon": horizon}


def days_with_range(bars, spec, range_name):
    name = range_name or spec.get("default_range")
    z = spec["ranges"][name]["tz"]
    out = []
    for d in sorted({B.local_date(b[0], z) for b in bars}):
        w = window(spec, name, d)
        if any(w["start"] <= b[0] < w["end"] for b in bars):
            out.append(d)
    return out


def evaluate(bars, spec, range_name=None, day=None, setup="break", direction="any",
             now=None, tf_min=None, min_range_atr=None, max_range_atr=None):
    """Where a setup stands on one day, using only bars closed by `now` (epoch)."""
    if setup not in SETUPS:
        raise ValueError("setup must be one of %s" % (SETUPS,))
    tf = int(tf_min or B.tf_of(bars))
    name = range_name or spec.get("default_range")
    z = spec["ranges"][name]["tz"]
    if day is None:
        ref = now if now is not None else (bars[-1][0] if bars else 0)
        day = tz.to_local(tz.from_epoch(ref), z).date()
        prev = window(spec, name, day - _dt.timedelta(days=1))
        if ref < prev["until"]:   # yesterday's range is still live (ranges that run past midnight)
            day -= _dt.timedelta(days=1)
    w = window(spec, name, day)
    now = now if now is not None else 10 ** 12
    closed = [b for b in bars if b[0] + tf * 60 <= now]
    out = {"symbol": spec["symbol"], "setup": setup, "range": name, "day": day.isoformat(),
           "window": w, "tf_min": tf, "state": "no_data"}
    rbars = [b for b in closed if w["start"] <= b[0] < w["end"]]
    if now < w["end"]:
        out["state"] = "forming" if rbars else "waiting_for_range"
        if rbars:
            out.update(range_high=max(b[2] for b in rbars), range_low=min(b[3] for b in rbars))
        return out
    full = [b for b in bars if w["start"] <= b[0] < w["end"]]
    expect = max(1, (w["end"] - w["start"]) // (tf * 60))
    if not full or len(full) < max(1, int(expect * 0.6)):
        out["state"] = "no_data"
        out["note"] = "range has %d of %d bars" % (len(full), expect)
        return out
    hi, lo = max(b[2] for b in full), min(b[3] for b in full)
    out.update(range_high=hi, range_low=lo, range_mid=(hi + lo) / 2, range_bars=len(full))
    prior = [b for b in bars if b[0] < w["start"]][-14 * 288:]
    days_prior, _ = B.daily(prior, z)
    datr = B.atr(days_prior[-15:], 14) if len(days_prior) >= 3 else None
    batr = B.atr([b for b in bars if b[0] < w["end"]][-200:], 14)
    out["daily_atr"], out["bar_atr"] = datr, batr
    if datr:
        out["range_atr"] = (hi - lo) / datr
        if min_range_atr is not None and out["range_atr"] < min_range_atr:
            out.update(state="filtered", note="range %.2f x daily ATR, below %.2f" % (out["range_atr"], min_range_atr))
            return out
        if max_range_atr is not None and out["range_atr"] > max_range_atr:
            out.update(state="filtered", note="range %.2f x daily ATR, above %.2f" % (out["range_atr"], max_range_atr))
            return out
    after = [b for b in closed if w["end"] <= b[0] and b[0] + tf * 60 <= w["until"]]
    for b in after:
        side = None
        if setup == "break":
            if b[4] > hi:
                side = "long"
            elif b[4] < lo:
                side = "short"
        else:
            swept_low = b[3] < lo and b[4] > lo
            swept_high = b[2] > hi and b[4] < hi
            if swept_low and not swept_high:
                side = "long"
            elif swept_high and not swept_low:
                side = "short"
        if side and direction in ("any", side):
            out.update(state="triggered", side=side, trigger_t=b[0], trigger_close_t=b[0] + tf * 60,
                       entry=b[4], trigger_bar=list(b),
                       extreme=(b[3] if side == "long" else b[2]))
            return out
    out["state"] = "expired" if now >= w["until"] else "waiting"
    if out["state"] == "waiting" and closed:
        out["last_close"] = closed[-1][4]
        out["distance_to_high"] = hi - closed[-1][4]
        out["distance_to_low"] = closed[-1][4] - lo
    return out
