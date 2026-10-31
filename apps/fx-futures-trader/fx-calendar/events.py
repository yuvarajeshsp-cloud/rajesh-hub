#!/usr/bin/env python3
"""Economic calendar and news blackout.

  events.py fetch                                  # this week's ForexFactory calendar
  events.py upcoming --hours 24 --symbols XAUUSD,ES
  events.py blackout XAUUSD [--at "2026-11-06 19:00"]
  events.py add --title "RBI policy" --country INR --at "2026-12-05 10:00" --tz Asia/Kolkata
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fx-core"))

from fxcore import cli_setup, events as E, instruments as I, store  # noqa: E402


def cmd_fetch(args):
    evs = E.fetch()
    data = E.save(evs)
    hi = [e for e in evs if e["impact"] == "High"]
    print("fetched %d events (%d high impact) -> %s" % (len(evs), len(hi), store.path("events.json")))
    print("calendar now holds %d events, updated %s" % (len(data["events"]), data["updated"]))
    return 0


def _symbols(args, config):
    return [s.strip() for s in (args.symbols.split(",") if args.symbols else config["watchlist"]) if s.strip()]


def cmd_upcoming(args):
    config = store.load_config()
    zone = config.get("display_tz", "UTC")
    now = store.now_utc(args.now, zone)
    evs, updated = E.load_all()
    if not evs:
        print("No events stored. Run: events.py fetch")
        return 1
    impacts = tuple(args.impact.split(",")) if args.impact else tuple(config["limits"]["news_impacts"])
    specs = I.load_all()
    ccys = set()
    for s in _symbols(args, config):
        try:
            ccys |= set(I.get(s, specs).get("currencies", []))
        except KeyError as e:
            print(e)
    end = now.timestamp() + args.hours * 3600
    shown = 0
    print("Events in the next %d h for %s (impact %s), times in %s\n" % (args.hours, ", ".join(sorted(ccys)) or "all", "/".join(impacts), zone))
    for e in evs:
        t = store.parse_iso(e["t"]).timestamp()
        if now.timestamp() - 3600 <= t <= end and e.get("impact") in impacts and (not ccys or e["country"] in ccys or e["country"] == "ALL"):
            print("%-22s %-4s %-7s %-40s fcst %-8s prev %s" % (store.fmt_t(store.parse_iso(e["t"]), zone, True), e["country"],
                  e.get("impact", ""), e["title"][:40], e.get("forecast", "") or "-", e.get("previous", "") or "-"))
            shown += 1
    if not shown:
        print("none")
    if updated:
        age = (now - store.parse_iso(updated)).total_seconds() / 3600
        if age > 24:
            print("\nwarning: calendar fetched %.0f hours ago; run events.py fetch" % age)
    return 0


def cmd_blackout(args):
    config = store.load_config()
    spec = I.get(args.symbol)
    at = store.now_utc(args.at, config.get("display_tz", "UTC"))
    clear, ev, mins, age = E.blackout(spec, at, config)
    if clear:
        print("CLEAR: no %s-impact event for %s within -%d/+%d min of %s" % (
            "/".join(config["limits"]["news_impacts"]), "/".join(spec["currencies"]),
            config["limits"]["news_blackout_after_min"], config["limits"]["news_blackout_before_min"],
            store.fmt_t(at, config.get("display_tz", "UTC"), True)))
    else:
        print("BLACKOUT: %s %s %s (%s, %+.0f min)" % (ev["country"], ev["impact"], ev["title"],
              store.fmt_t(store.parse_iso(ev["t"]), config.get("display_tz", "UTC"), True), mins))
    if age is None or age > 24 * 7:
        print("warning: calendar missing or older than a week; run events.py fetch")
    return 0 if clear else 2


def cmd_add(args):
    t = store.iso(store.tz.parse_local(args.at, args.tz))
    lst = store.read_json(store.path("events.manual.json"), [])
    lst.append({"title": args.title, "country": args.country.upper(), "t": t, "impact": args.impact})
    store.write_json(store.path("events.manual.json"), lst)
    print("added %s %s at %s -> %s" % (args.country.upper(), args.title, t, store.path("events.manual.json")))
    return 0


def main(argv=None):
    cli_setup()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    up = sub.add_parser("upcoming")
    up.add_argument("--hours", type=int, default=24)
    up.add_argument("--symbols")
    up.add_argument("--impact", help="High,Medium")
    up.add_argument("--now")
    bo = sub.add_parser("blackout")
    bo.add_argument("symbol")
    bo.add_argument("--at")
    ad = sub.add_parser("add")
    ad.add_argument("--title", required=True)
    ad.add_argument("--country", required=True, help="currency code (INR, USD...), a symbol (NIFTY), or ALL")
    ad.add_argument("--at", required=True)
    ad.add_argument("--tz", default="Asia/Kolkata")
    ad.add_argument("--impact", default="High")
    args = ap.parse_args(argv)
    return {"fetch": cmd_fetch, "upcoming": cmd_upcoming, "blackout": cmd_blackout, "add": cmd_add}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
