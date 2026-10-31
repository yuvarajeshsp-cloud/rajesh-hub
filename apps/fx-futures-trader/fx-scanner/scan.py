#!/usr/bin/env python3
"""Chart scanner: range breakouts and liquidity sweeps across forex, gold,
CME futures and MCX/NSE futures.

  scan.py                                  # the watchlist in trader/config.json
  scan.py --symbols EURUSD,XAUUSD,ES --setup sweep --range london
  scan.py list                             # every instrument and its spec status
  scan.py import XAUUSD export.csv --csv-tz NY+7   # load an MT5/NinjaTrader export
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fx-core"))

from fxcore import bars as B, cli_setup, instruments as I, setups as S, store, tz  # noqa: E402


def scan_one(spec, args, config, now_t):
    data, src = B.load(spec, args.tf, args.source, config=config, offline=args.offline)
    if not data:
        return [{"symbol": spec["symbol"], "state": "no_data", "source": src}]
    rows = []
    setups = S.SETUPS if args.setup == "both" else (args.setup,)
    ranges = [args.range] if args.range else [spec.get("default_range")]
    if args.range == "all":
        ranges = list(spec.get("ranges", {}))
    for rn in ranges:
        if rn not in spec.get("ranges", {}):
            continue
        for st in setups:
            ev = S.evaluate(data, spec, rn, setup=st, direction=args.direction, now=now_t, tf_min=args.tf,
                            min_range_atr=args.min_range_atr, max_range_atr=args.max_range_atr)
            ev["source"] = src
            closes = [b[4] for b in data if b[0] < now_t][-50 * (1440 // args.tf):]
            dly, _ = B.daily([b for b in data if b[0] < now_t], spec["ranges"][rn]["tz"])
            if len(dly) >= 20:
                e20 = B.ema([d[4] for d in dly], 20)
                ev["trend"] = "up" if dly[-1][4] > e20 else "down"
            ev["last"] = closes[-1] if closes else None
            rows.append(ev)
    return rows


def fmt_row(ev, spec, config):
    w = ev.get("window") or {}
    z = w.get("tz", "UTC")
    p = lambda x: I.fmt_price(x, spec) if isinstance(x, (int, float)) else "-"
    rng = "%s-%s" % (p(ev.get("range_low")), p(ev.get("range_high"))) if "range_high" in ev else "-"
    ratr = ("%.2fx" % ev["range_atr"]) if ev.get("range_atr") else "-"
    extra = ""
    if ev["state"] == "triggered":
        extra = "%s at %s, close %s" % (ev["side"].upper(), store.fmt_both(ev["trigger_close_t"], z, config), p(ev["entry"]))
    elif ev["state"] == "waiting" and "distance_to_high" in ev:
        extra = "last %s, %s to high, %s to low" % (p(ev["last_close"]), p(ev["distance_to_high"]), p(ev["distance_to_low"]))
    elif ev.get("note"):
        extra = ev["note"]
    return "%-14s %-6s %-6s %-11s %-25s %-6s %-5s %s" % (
        ev["symbol"], ev.get("range", "-"), ev.get("setup", "-"), ev["state"], rng, ratr, ev.get("trend", "-"), extra)


def cmd_scan(args):
    config = store.load_config()
    specs = I.load_all()
    syms = [s.strip() for s in (args.symbols.split(",") if args.symbols else config["watchlist"]) if s.strip()]
    now = store.now_utc(args.now, config.get("display_tz", "UTC"))
    now_t = tz.epoch(now)
    out, errors = [], []
    print("Scan at %s   setup=%s tf=%dm\n" % (store.fmt_t(now, config.get("display_tz", "UTC"), True), args.setup, args.tf))
    print("%-14s %-6s %-6s %-11s %-25s %-6s %-5s %s" % ("symbol", "range", "setup", "state", "range low-high", "R/ATR", "trend", "detail"))
    for sym in syms:
        try:
            spec = I.get(sym, specs)
            for ev in scan_one(spec, args, config, now_t):
                out.append(ev)
                print(fmt_row(ev, spec, config))
        except Exception as e:
            errors.append("%s: %s" % (sym, e))
            print("%-14s error: %s" % (sym, e))
    trig = [e for e in out if e["state"] == "triggered"]
    print("\n%d triggered of %d checked." % (len(trig), len(out)))
    for e in out:
        if "proxy" in str(e.get("source", "")):
            print("note: %s uses %s data; prices differ from your broker's." % (e["symbol"], e["source"]))
            break
    if args.write:
        store.write_json(store.path("scan.json"), {"at": store.iso(now), "results": out, "errors": errors})
        print("wrote", store.path("scan.json"))
    return 0


def cmd_list(args):
    specs = I.load_all()
    print("%-15s %-6s %-6s %-9s %-10s %-8s %-22s %s" % ("symbol", "class", "venue", "tick", "tick val", "ccy", "execution", "spec"))
    for k in sorted(specs, key=lambda s: (specs[s].get("class", ""), s)):
        s = specs[k]
        brokers = ", ".join(s.get("brokers", {})) or "signals only"
        print("%-15s %-6s %-6s %-9s %-10s %-8s %-22s %s" % (
            k, s.get("class"), s.get("venue", "-"), s["tick_size"], s["tick_value"], s["value_ccy"], brokers,
            "ok" if s.get("verified") else "VERIFY"))
    return 0


def cmd_import(args):
    config = store.load_config()
    spec = I.get(args.symbol)
    data, src = B.load(spec, args.tf, csv_path=args.file, csv_tz=args.csv_tz, config=config)
    zone = config.get("display_tz", "UTC")
    print("imported %d bars of %s (%s) from %s to %s" % (len(data), spec["symbol"], src,
          store.fmt_t(data[0][0], zone, True), store.fmt_t(data[-1][0], zone, True)) if data else "no bars read")
    return 0 if data else 1


def main(argv=None):
    cli_setup()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sc = sub.add_parser("scan")
    for p in (ap, sc):
        p.add_argument("--symbols")
        p.add_argument("--setup", default="break", choices=["break", "sweep", "both"])
        p.add_argument("--range", help="range name, or 'all'")
        p.add_argument("--direction", default="any", choices=["any", "long", "short"])
        p.add_argument("--tf", type=int, default=5)
        p.add_argument("--source", default="auto", choices=["auto", "cache", "yahoo", "mt5"])
        p.add_argument("--offline", action="store_true")
        p.add_argument("--min-range-atr", type=float)
        p.add_argument("--max-range-atr", type=float)
        p.add_argument("--now")
        p.add_argument("--write", action="store_true")
    sub.add_parser("list")
    im = sub.add_parser("import")
    im.add_argument("symbol")
    im.add_argument("file")
    im.add_argument("--csv-tz", default=None, help="clock of the file: UTC, UTC+3, NY+7 (MT5 servers), Asia/Kolkata...")
    im.add_argument("--tf", type=int, default=5)
    args = ap.parse_args(argv)
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "import":
        return cmd_import(args)
    return cmd_scan(args)


if __name__ == "__main__":
    sys.exit(main())
