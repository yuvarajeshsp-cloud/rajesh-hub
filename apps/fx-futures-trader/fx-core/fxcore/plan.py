"""Exit plans (stop, scale-out targets, breakeven, flat-by) and the bar-by-bar
trade walk shared by the time machine's simulations and its history check."""

import random

from . import instruments as I
from . import store

STOPS = "range_mid | range_far | extreme[:ticks] | atr:K | ticks:N | price:P"


def stop_price(ev, spec, method):
    side = ev["side"]
    entry = ev["entry"]
    m, _, arg = method.partition(":")
    if m == "range_mid":
        s = ev["range_mid"]
    elif m == "range_far":
        s = ev["range_low"] if side == "long" else ev["range_high"]
    elif m == "extreme":
        buf = float(arg or 0) * spec["tick_size"]
        s = ev["extreme"] - buf if side == "long" else ev["extreme"] + buf
    elif m == "atr":
        a = ev.get("bar_atr")
        if not a:
            raise ValueError("no ATR available for atr stop")
        k = float(arg or 1.5)
        s = entry - k * a if side == "long" else entry + k * a
    elif m == "ticks":
        d = float(arg) * spec["tick_size"]
        s = entry - d if side == "long" else entry + d
    elif m == "price":
        s = float(arg)
    else:
        raise ValueError("stop must be " + STOPS)
    return I.round_tick(s, spec, "down" if side == "long" else "up")


def build(ev, spec, stop="range_mid", targets_r=(1, 2, 3), split=None, be_after_tp1=True,
          entry=None, min_stop_ticks=1):
    if ev.get("state") != "triggered":
        raise ValueError("setup is %s, not triggered" % ev.get("state"))
    side = ev["side"]
    e = I.round_tick(entry if entry is not None else ev["entry"], spec)
    ev = dict(ev, entry=e)
    s = stop_price(ev, spec, stop)
    risk = (e - s) if side == "long" else (s - e)
    if risk <= 0 or I.ticks(risk, spec) < min_stop_ticks - 1e-9:
        raise ValueError("stop %s is not beyond entry %s for a %s" % (s, e, side))
    targets_r = [float(r) for r in targets_r]
    split = list(split) if split else [1.0 / len(targets_r)] * len(targets_r)
    if len(split) != len(targets_r):
        split = [1.0 / len(targets_r)] * len(targets_r)
    tot = sum(split)
    split = [x / tot for x in split]
    tps = []
    for r, wgt in zip(targets_r, split):
        p = e + r * risk if side == "long" else e - r * risk
        tps.append({"r": r, "price": I.round_tick(p, spec, "nearest"), "weight": round(wgt, 4)})
    w = ev["window"]
    return {
        "symbol": spec["symbol"], "side": side, "entry": e, "stop": s,
        "risk": round(risk, 10), "risk_ticks": round(I.ticks(risk, spec), 2),
        "targets": tps, "be_after_tp1": bool(be_after_tp1),
        "rr": round(sum(t["r"] * t["weight"] for t in tps), 3),
        "signal_t": store.iso(store.tz.from_epoch(ev["trigger_close_t"])),
        "valid_until": store.iso(store.tz.from_epoch(w["until"])),
        "flat_by": store.iso(store.tz.from_epoch(w["flat_by"])) if w.get("flat_by") else None,
        "horizon": store.iso(store.tz.from_epoch(w["horizon"])),
        "range": {"name": ev["range"], "high": ev["range_high"], "low": ev["range_low"], "day": ev["day"]},
        "rule": {"setup": ev["setup"], "range": ev["range"], "stop": stop, "targets_r": targets_r,
                 "split": split, "be_after_tp1": bool(be_after_tp1)},
    }


def walk(path, side, entry, stop, targets, be_after_tp1=True):
    """Walk a trade through bars (o, h, l, c). A bar that touches both the stop
    and a target counts as the stop (we cannot see inside the bar)."""
    risk = (entry - stop) if side == "long" else (stop - entry)
    open_w = 1.0
    r_total = 0.0
    hits = 0
    cur_stop = stop
    stopped = False
    for b in path:
        o, h, l, c = b[-4:] if len(b) == 4 else b[1:5]
        hit_stop = (l <= cur_stop) if side == "long" else (h >= cur_stop)
        if hit_stop:
            fill = cur_stop
            if (side == "long" and o < cur_stop) or (side == "short" and o > cur_stop):
                fill = o   # gapped through the stop
            r = ((fill - entry) if side == "long" else (entry - fill)) / risk
            r_total += open_w * r
            open_w = 0.0
            stopped = True
            break
        for i in range(hits, len(targets)):
            t = targets[i]
            if (side == "long" and h >= t["price"]) or (side == "short" and l <= t["price"]):
                r_total += t["weight"] * t["r"]
                open_w -= t["weight"]
                hits = i + 1
                if hits == 1 and be_after_tp1:
                    cur_stop = entry
            else:
                break
        if open_w <= 1e-9:
            break
    if open_w > 1e-9 and not stopped:
        lc = path[-1][4] if path and len(path[-1]) > 4 else (path[-1][3] if path else entry)
        r_total += open_w * (((lc - entry) if side == "long" else (entry - lc)) / risk)
    if stopped and hits == 0:
        outcome = "stop"
    elif hits:
        outcome = "tp%d" % hits
    else:
        outcome = "open"
    return {"outcome": outcome, "r": round(r_total, 4), "targets_hit": hits, "stopped": stopped,
            "stopped_at_be": stopped and hits > 0 and be_after_tp1}


# ---------------------------------------------------------------- Monte Carlo

def slot_library(past_bars, tf_min, zone, minute_of_day):
    """Per time-of-day slot, the bar shapes seen there, relative to the bar
    before: (o/pc, h/pc, l/pc, c/pc). Only consecutive bars are used."""
    lib = {}
    step = tf_min * 60
    for a, b in zip(past_bars, past_bars[1:]):
        if b[0] - a[0] != step or a[4] <= 0:
            continue
        k = minute_of_day(b[0])
        lib.setdefault(k, []).append((b[1] / a[4], b[2] / a[4], b[3] / a[4], b[4] / a[4]))
    return lib


def simulate(plan_, start_price, slots, lib, n=10000, seed=7):
    rng = random.Random(seed)
    targets = plan_["targets"]
    side, entry, stop, be = plan_["side"], plan_["entry"], plan_["stop"], plan_["be_after_tp1"]
    usable = [k for k in slots if lib.get(k)]
    counts = {"stop": 0, "open": 0}
    for i in range(len(targets)):
        counts["tp%d" % (i + 1)] = 0
    reached = [0] * len(targets)
    rs = []
    for _ in range(n):
        pc = start_price
        path = []
        for k in usable:
            ro, rh, rl, rc = rng.choice(lib[k])
            path.append((pc * ro, pc * rh, pc * rl, pc * rc))
            pc = pc * rc
        res = walk(path, side, entry, stop, targets, be)
        counts[res["outcome"]] += 1
        for j in range(res["targets_hit"]):
            reached[j] += 1
        rs.append(res["r"])
    rs.sort()
    return {
        "runs": n, "seed": seed, "slots": len(usable),
        "outcomes": {k: round(v / n, 4) for k, v in counts.items()},
        "reached_target": [round(x / n, 4) for x in reached],
        "mean_r": round(sum(rs) / n, 3), "median_r": rs[n // 2],
        "p5_r": rs[int(n * 0.05)], "p95_r": rs[int(n * 0.95)],
        "win_rate": round(sum(1 for r in rs if r > 0) / n, 4),
    }
