#!/usr/bin/env python3
"""Entry timer and exit planner.

  plan.py check XAUUSD --setup sweep --range london      # waiting / triggered / expired
  plan.py watch ES --every 30                            # re-check until it triggers
  plan.py make XAUUSD --setup sweep --stop extreme:20 --targets 1,2,3 --write
  plan.py manual XAUUSD --side long --entry 2650.20 --stop 2644.80 --write
"""

import argparse
import datetime as _dt
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fx-core"))

from fxcore import bars as B, cli_setup, instruments as I, plan as P, setups as S, store, tz  # noqa: E402


def _eval(args, config, spec, now_t, refresh=True):
    data, src = B.load(spec, args.tf, "cache" if not refresh else args.source, config=config, offline=args.offline)
    ev = S.evaluate(data, spec, args.range, setup=args.setup, direction=args.direction, now=now_t, tf_min=args.tf)
    ev["source"] = src
    return ev


def describe(ev, spec, config):
    w = ev["window"]
    z = w["tz"]
    p = lambda x: I.fmt_price(x, spec)
    head = "%s %s %s range (%s to %s, valid until %s)" % (spec["symbol"], ev["range"], ev["setup"],
            store.fmt_t(w["start"], z), store.fmt_t(w["end"], z), store.fmt_both(w["until"], z, config))
    lines = [head]
    if "range_high" in ev:
        lines.append("range %s - %s" % (p(ev["range_low"]), p(ev["range_high"])))
    st = ev["state"]
    if st == "triggered":
        lines.append("TRIGGERED %s: bar closing %s closed at %s" % (ev["side"].upper(), store.fmt_both(ev["trigger_close_t"], z, config), p(ev["entry"])))
    elif st == "waiting":
        lines.append("WAITING: no closed bar has %s yet" % ("closed beyond the range" if ev["setup"] == "break" else "swept and closed back inside"))
    elif st == "forming":
        lines.append("FORMING: the range is still being built until %s" % store.fmt_t(w["end"], z))
    elif st == "waiting_for_range":
        lines.append("NOT STARTED: the range starts %s" % store.fmt_both(w["start"], z, config, True))
    elif st == "expired":
        lines.append("EXPIRED: no trigger before %s" % store.fmt_t(w["until"], z))
    else:
        lines.append("%s %s" % (st.upper(), ev.get("note", "")))
    return "\n".join(lines)


def describe_plan(pl, spec, config):
    z = spec["ranges"][pl["range"]["name"]]["tz"] if pl.get("range") else config.get("display_tz", "UTC")
    p = lambda x: I.fmt_price(x, spec)
    out = ["PLAN %s %s" % (pl["side"].upper(), pl["symbol"]),
           "  entry  %s" % p(pl["entry"]),
           "  stop   %s  (%s ticks, %s a unit at risk)" % (p(pl["stop"]), ("%g" % pl["risk_ticks"]), p(pl["risk"]))]
    for i, t in enumerate(pl["targets"], 1):
        out.append("  TP%d    %s  (%gR, %d%% of the position)" % (i, p(t["price"]), t["r"], round(t["weight"] * 100)))
    out.append("  after TP1: %s" % ("stop moves to breakeven" if pl["be_after_tp1"] else "stop stays"))
    out.append("  reward/risk (weighted): %.2f" % pl["rr"])
    if pl.get("flat_by"):
        out.append("  flat by %s" % store.fmt_both(store.parse_iso(pl["flat_by"]), spec.get("session", {}).get("tz", z), config))
    else:
        out.append("  no flat-by time; the replay horizon is %s" % store.fmt_both(store.parse_iso(pl["horizon"]), z, config))
    return "\n".join(out)


def cmd_check(args):
    config = store.load_config()
    spec = I.get(args.symbol)
    now_t = tz.epoch(store.now_utc(args.now, config.get("display_tz", "UTC")))
    ev = _eval(args, config, spec, now_t)
    print(describe(ev, spec, config))
    return 0 if ev["state"] == "triggered" else 3


def cmd_watch(args):
    config = store.load_config()
    spec = I.get(args.symbol)
    deadline = time.time() + args.max_min * 60
    while True:
        now_t = tz.epoch(store.now_utc(None))
        ev = _eval(args, config, spec, now_t)
        stamp = store.fmt_t(now_t, config.get("display_tz", "UTC"))
        print("[%s] %s" % (stamp, describe(ev, spec, config).splitlines()[-1]), flush=True)
        if ev["state"] in ("triggered", "expired", "no_data", "filtered") or time.time() > deadline:
            return 0 if ev["state"] == "triggered" else 3
        time.sleep(max(5, args.every))


def _write(pl, args):
    pl["created"] = store.iso(store.now_utc(args.now))
    if args.write:
        store.write_json(store.path("plan.json"), pl)
        print("\nwrote", store.path("plan.json"))


def cmd_make(args):
    config = store.load_config()
    spec = I.get(args.symbol)
    now_t = tz.epoch(store.now_utc(args.now, config.get("display_tz", "UTC")))
    ev = _eval(args, config, spec, now_t)
    print(describe(ev, spec, config))
    if ev["state"] != "triggered":
        print("\nNo plan: the setup has not triggered.")
        return 3
    targets = [float(x) for x in (args.targets.split(",") if args.targets else config["plan"]["targets_r"])]
    split = [float(x) for x in args.split.split(",")] if args.split else (config["plan"]["split"] if len(config["plan"]["split"]) == len(targets) else None)
    be = config["plan"]["be_after_tp1"] if args.be is None else args.be
    pl = P.build(ev, spec, stop=args.stop, targets_r=targets, split=split, be_after_tp1=be, entry=args.entry)
    pl["source"] = ev.get("source")
    print()
    print(describe_plan(pl, spec, config))
    _write(pl, args)
    return 0


def cmd_manual(args):
    """A discretionary trade: you give side, entry and stop; the targets come from R."""
    config = store.load_config()
    spec = I.get(args.symbol)
    now = store.now_utc(args.now, config.get("display_tz", "UTC"))
    rn = args.range or spec.get("default_range")
    z = spec["ranges"][rn]["tz"]
    day = tz.to_local(now, z).date()
    w = S.window(spec, rn, day)
    if tz.epoch(now) > w["horizon"]:
        w = S.window(spec, rn, day + _dt.timedelta(days=1))
    w = dict(w, until=max(w["until"], tz.epoch(now) + 3600))
    ev = {"state": "triggered", "side": args.side, "entry": args.entry, "setup": "manual", "range": rn,
          "day": day.isoformat(), "window": w, "range_high": None, "range_low": None, "range_mid": None,
          "trigger_close_t": tz.epoch(now), "extreme": args.stop}
    targets = [float(x) for x in (args.targets.split(",") if args.targets else config["plan"]["targets_r"])]
    split = [float(x) for x in args.split.split(",")] if args.split else (config["plan"]["split"] if len(config["plan"]["split"]) == len(targets) else None)
    be = config["plan"]["be_after_tp1"] if args.be is None else args.be
    pl = P.build(ev, spec, stop="price:%s" % args.stop, targets_r=targets, split=split, be_after_tp1=be)
    pl["range"] = {"name": rn, "high": None, "low": None, "day": day.isoformat()}
    print(describe_plan(pl, spec, config))
    _write(pl, args)
    return 0


def main(argv=None):
    cli_setup()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("symbol")
        p.add_argument("--setup", default="break", choices=list(S.SETUPS))
        p.add_argument("--range")
        p.add_argument("--direction", default="any", choices=["any", "long", "short"])
        p.add_argument("--tf", type=int, default=5)
        p.add_argument("--source", default="auto", choices=["auto", "cache", "yahoo", "mt5"])
        p.add_argument("--offline", action="store_true")
        p.add_argument("--now")

    def planargs(p):
        p.add_argument("--targets", help="R multiples, e.g. 1,2,3")
        p.add_argument("--split", help="share of the position per target, e.g. 0.34,0.33,0.33")
        p.add_argument("--be", dest="be", action="store_true", default=None, help="stop to breakeven after TP1")
        p.add_argument("--no-be", dest="be", action="store_false")
        p.add_argument("--write", action="store_true")

    for name in ("check", "watch", "make"):
        p = sub.add_parser(name)
        common(p)
        if name == "watch":
            p.add_argument("--every", type=int, default=30)
            p.add_argument("--max-min", type=int, default=120)
        if name == "make":
            p.add_argument("--stop", default="range_mid", help=P.STOPS)
            p.add_argument("--entry", type=float, help="your actual or intended entry price")
            planargs(p)
    m = sub.add_parser("manual")
    m.add_argument("symbol")
    m.add_argument("--side", required=True, choices=["long", "short"])
    m.add_argument("--entry", type=float, required=True)
    m.add_argument("--stop", type=float, required=True)
    m.add_argument("--range")
    m.add_argument("--now")
    planargs(m)
    args = ap.parse_args(argv)
    return {"check": cmd_check, "watch": cmd_watch, "make": cmd_make, "manual": cmd_manual}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
