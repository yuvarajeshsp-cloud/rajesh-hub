#!/usr/bin/env python3
"""Time machine: before you risk money, replay the rest of the session
thousands of times from the instrument's own recent bars, and re-run the same
rule on every past session it fired.

  replay.py run                         # reads trader/plan.json
  replay.py run --runs 20000 --seed 19 --sessions 60 --write
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fx-core"))

from fxcore import bars as B, cli_setup, instruments as I, plan as P, setups as S, store, tz  # noqa: E402


def history(data, spec, pl, before_t, sessions):
    rule = pl["rule"]
    if rule["setup"] == "manual":
        return None
    days = [d for d in S.days_with_range([b for b in data if b[0] < before_t], spec, rule["range"])][-sessions:]
    tally = {"fired": 0, "same_side": 0, "outcomes": {}, "r": [], "trades": []}
    for d in days:
        ev = S.evaluate(data, spec, rule["range"], day=d, setup=rule["setup"], direction="any")
        if ev["state"] != "triggered":
            continue
        try:
            hp = P.build(ev, spec, stop=rule["stop"], targets_r=rule["targets_r"], split=rule["split"],
                         be_after_tp1=rule["be_after_tp1"])
        except ValueError:
            continue
        end = ev["window"]["horizon"]
        path = [b for b in data if ev["trigger_close_t"] <= b[0] < end]
        if not path:
            continue
        res = P.walk(path, hp["side"], hp["entry"], hp["stop"], hp["targets"], hp["be_after_tp1"])
        tally["fired"] += 1
        tally["same_side"] += hp["side"] == pl["side"]
        tally["outcomes"][res["outcome"]] = tally["outcomes"].get(res["outcome"], 0) + 1
        tally["r"].append(res["r"])
        tally["trades"].append({"day": d.isoformat(), "side": hp["side"], "entry": hp["entry"], "outcome": res["outcome"], "r": res["r"]})
    tally["sessions"] = len(days)
    tally["mean_r"] = round(sum(tally["r"]) / len(tally["r"]), 3) if tally["r"] else None
    tally["win_rate"] = round(sum(1 for r in tally["r"] if r > 0) / len(tally["r"]), 3) if tally["r"] else None
    return tally


def verdict(mc, hist):
    m = mc["mean_r"]
    n = (hist or {}).get("fired", 0)
    hm = (hist or {}).get("mean_r")
    if m > 0.15 and (hm is None or hm > 0.1):
        v = "leans positive"
    elif m < -0.15 or (hm is not None and hm < -0.15):
        v = "leans negative"
    else:
        v = "close to a coin flip"
    if hist is not None and n < 20:
        v += "; only %d past trades, too few to trust" % n
    return v


def cmd_run(args):
    config = store.load_config()
    pl = store.read_json(args.plan or store.path("plan.json"))
    if not pl:
        print("No plan. Run fx-entry-exit first: plan.py make SYMBOL --write")
        return 1
    spec = I.get(pl["symbol"])
    data, src = B.load(spec, args.tf, args.source, config=config, offline=args.offline)
    if not data:
        print("no bars for", pl["symbol"])
        return 1
    tf = args.tf
    start_t = int(store.parse_iso(pl["signal_t"]).timestamp())
    end_t = int(store.parse_iso(pl["flat_by"] or pl["horizon"]).timestamp())
    rn = pl["range"]["name"]
    z = spec["ranges"][rn]["tz"]
    day0 = tz.to_local(tz.from_epoch(start_t), z).date()
    day_start = S.window(spec, rn, day0)["start"]

    def mod(t):
        lt = tz.to_local(tz.from_epoch(t), z)
        return lt.hour * 60 + lt.minute

    past_days = sorted({B.local_date(b[0], z) for b in data if b[0] < day_start})[-args.sessions:]
    keep = set(past_days)
    past = [b for b in data if b[0] < day_start and B.local_date(b[0], z) in keep]
    lib = P.slot_library(past, tf, z, mod)
    slots = [mod(t) for t in range(start_t, end_t, tf * 60)]
    if not [k for k in slots if lib.get(k)]:
        print("No past bars at these times of day to replay from.")
        return 1
    mc = P.simulate(pl, pl["entry"], slots, lib, n=args.runs, seed=args.seed)
    hist = history(data, spec, pl, day_start, args.sessions)
    v = verdict(mc, hist)

    p = lambda x: I.fmt_price(x, spec)
    print("TIME MACHINE  %s %s from %s, entry %s, stop %s, targets %s" % (
        pl["side"].upper(), pl["symbol"], store.fmt_both(start_t, z, config), p(pl["entry"]), p(pl["stop"]),
        " / ".join(p(t["price"]) for t in pl["targets"])))
    print("data: %s, %d past sessions, %d-minute bars, until %s\n" % (src, len(past_days), tf, store.fmt_t(end_t, z)))
    o = mc["outcomes"]
    print("%d replays (seed %d):" % (mc["runs"], mc["seed"]))
    print("  stop before TP1   %5.1f %%" % (100 * o.get("stop", 0)))
    for i, x in enumerate(mc["reached_target"], 1):
        print("  reached TP%d       %5.1f %%" % (i, 100 * x))
    print("  nothing hit       %5.1f %%  (closed at the end price)" % (100 * o.get("open", 0)))
    print("  average result    %+.2fR   (middle %+.2fR, worst 5%% %+.2fR, best 5%% %+.2fR)" % (mc["mean_r"], mc["median_r"], mc["p5_r"], mc["p95_r"]))
    print("  finished ahead    %5.1f %%" % (100 * mc["win_rate"]))
    if hist is not None:
        print("\nSame rule on the last %d real sessions: fired %d times (%d %s)" % (hist["sessions"], hist["fired"], hist["same_side"], pl["side"]))
        if hist["fired"]:
            print("  " + ", ".join("%s %d" % (k, v_) for k, v_ in sorted(hist["outcomes"].items())))
            print("  average %+.2fR, finished ahead %.0f %%" % (hist["mean_r"], 100 * hist["win_rate"]))
    else:
        print("\nManual plan: no rule to re-run on history.")
    print("\nVerdict: %s." % v)
    print("A simulation from %d sessions of bars, not a forecast: news, gaps and spread are not in it." % len(past_days))
    out = {"plan": pl, "source": src, "monte_carlo": mc, "history": hist, "verdict": v, "at": store.iso(store.now_utc(args.now))}
    if args.write:
        store.write_json(store.path("replay.json"), out)
        print("wrote", store.path("replay.json"))
    return 0


def main(argv=None):
    cli_setup()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--plan")
    r.add_argument("--runs", type=int, default=10000)
    r.add_argument("--seed", type=int, default=7)
    r.add_argument("--sessions", type=int, default=60)
    r.add_argument("--tf", type=int, default=5)
    r.add_argument("--source", default="cache", choices=["auto", "cache", "yahoo", "mt5"])
    r.add_argument("--offline", action="store_true")
    r.add_argument("--now")
    r.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
