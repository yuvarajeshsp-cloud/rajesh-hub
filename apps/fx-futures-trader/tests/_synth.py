"""Deterministic synthetic bars for offline tests (no network)."""

import datetime as _dt
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "fx-core"))

from fxcore import tz  # noqa: E402


def series(zone, start_day, days, open_hhmm, close_hhmm, price, vol, tf=5, seed=1, weekdays_only=True, drift=0.0):
    """Bars every tf minutes between open and close local time, each trading day."""
    rng = random.Random(seed)
    out = []
    d = start_day
    n = 0
    while n < days:
        if weekdays_only and d.weekday() >= 5:
            d += _dt.timedelta(days=1)
            continue
        o = tz.hhmm(open_hhmm)
        c = tz.hhmm(close_hhmm)
        t0 = tz.epoch(tz.to_utc(_dt.datetime.combine(d, o), zone))
        t1 = tz.epoch(tz.to_utc(_dt.datetime.combine(d if c > o else d + _dt.timedelta(days=1), c), zone))
        t = t0
        while t < t1:
            op = price
            cl = op + rng.gauss(drift, vol)
            hi = max(op, cl) + abs(rng.gauss(0, vol * 0.5))
            lo = min(op, cl) - abs(rng.gauss(0, vol * 0.5))
            out.append((t, round(op, 5), round(hi, 5), round(lo, 5), round(cl, 5), 100.0))
            price = cl
            t += tf * 60
        d += _dt.timedelta(days=1)
        n += 1
    return out


def at(day, hhmm, zone):
    return tz.epoch(tz.to_utc(_dt.datetime.combine(day, tz.hhmm(hhmm)), zone))


def shape_day(bars, zone, day, range_start, range_end, level, half_width, after_bars, tf=5):
    """Overwrite one day's range bars to sit in level +/- half_width, then the
    given `after_bars` list of (o, h, l, c) right after the range."""
    s, e = at(day, range_start, zone), at(day, range_end, zone)
    out = []
    after = list(after_bars)
    for b in bars:
        t = b[0]
        if s <= t < e:
            k = (t - s) // (tf * 60)
            mid = level + (half_width * 0.6 if k % 2 else -half_width * 0.6)
            out.append((t, level, level + half_width if k == 1 else max(level, mid) + 0.1,
                        level - half_width if k == 2 else min(level, mid) - 0.1, mid, 100.0))
        elif e <= t < e + len(after) * tf * 60:
            o, h, l, c = after[(t - e) // (tf * 60)]
            out.append((t, o, h, l, c, 100.0))
        else:
            out.append(b)
    return out
