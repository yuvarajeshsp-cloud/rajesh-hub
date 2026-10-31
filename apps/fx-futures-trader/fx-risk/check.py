#!/usr/bin/env python3
"""Risk gate: PASS or BLOCK for every proposed order, with the reason.

  check.py                          # checks trader/orders.json, records verdicts
  check.py --price 2654.6 --spread 25   # also check live price drift and spread (ticks)
"""

import argparse
import datetime as _dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fx-core"))

from fxcore import activity, cli_setup, events as E, instruments as I, ledger as L, orders as O, store, tz  # noqa: E402

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _limit_money(pct, money, balance):
    vals = [v for v in (money, (balance * pct / 100.0) if pct else None) if v]
    return min(vals) if vals else None


def check_open(o, spec, config, now, price=None, spread=None, events=None):
    lim = config["limits"]
    bal = float(config["account"]["balance"])
    ccy = o["account_ccy"]
    fails, warns = [], []

    if O.fingerprint(o) != o.get("fingerprint"):
        fails.append("order was edited after sizing (fingerprint mismatch); run size.py again")
    if not spec.get("verified") and spec["symbol"] not in lim.get("acknowledge_specs", []):
        fails.append("spec for %s is marked VERIFY; check tick size/value with your broker, then set verified=true "
                     "in trader/instruments.json or add it to limits.acknowledge_specs" % spec["symbol"])
    max_risk = _limit_money(lim.get("max_risk_pct"), lim.get("max_risk_money"), bal)
    if max_risk is not None and o["max_loss"] > max_risk + 1e-6:
        fails.append("max loss %s is over your per-trade limit %s" % (store.money(o["max_loss"], ccy), store.money(max_risk, ccy)))
    realized, open_risk, started = L.risk_today(config, now)
    daily = _limit_money(lim.get("daily_loss_limit_pct"), lim.get("daily_loss_limit_money"), bal)
    if daily is not None:
        worst = max(0.0, -realized) + open_risk + o["max_loss"]
        if worst > daily + 1e-6:
            fails.append("daily loss limit %s: lost %s today, %s open at stops, this adds %s" % (
                store.money(daily, ccy), store.money(max(0.0, -realized), ccy), store.money(open_risk, ccy), store.money(o["max_loss"], ccy)))
    if lim.get("max_trades_per_day") is not None and len(started) >= lim["max_trades_per_day"]:
        fails.append("already %d trades today (limit %d)" % (len(started), lim["max_trades_per_day"]))
    if lim.get("min_rr") and o["rr"] + 1e-9 < lim["min_rr"]:
        fails.append("reward/risk %.2f is under your minimum %.2f" % (o["rr"], lim["min_rr"]))
    if o["qty"] > float(spec["max_qty"]) + 1e-9:
        fails.append("size %g is over the %g maximum for %s" % (o["qty"], spec["max_qty"], spec["symbol"]))
    mq = (lim.get("max_qty") or {}).get(spec["symbol"])
    if mq is not None and o["qty"] > mq + 1e-9:
        fails.append("size %g is over your limit %g for %s" % (o["qty"], mq, spec["symbol"]))

    sig = store.parse_iso(o["signal_t"])
    age = (now - sig).total_seconds() / 60
    if lim.get("signal_max_age_min") is not None and age > lim["signal_max_age_min"]:
        fails.append("the signal is %.0f minutes old (limit %d); re-check the entry" % (age, lim["signal_max_age_min"]))
    if age < -1:
        fails.append("the signal time is in the future")
    if now >= store.parse_iso(o["valid_until"]):
        fails.append("past the entry window (%s)" % o["valid_until"])
    if o.get("flat_by") and now >= store.parse_iso(o["flat_by"]) - _dt.timedelta(minutes=10):
        fails.append("too close to the flat-by time %s" % o["flat_by"])

    clear, ev, mins, feed_age = E.blackout(spec, now, config, events)
    if not clear:
        fails.append("news blackout: %s %s %s (%+.0f min)" % (ev["country"], ev["impact"], ev["title"], mins))
    if feed_age is None and events is None:
        warns.append("no economic calendar stored; run fx-calendar events.py fetch")
    elif feed_age is not None and feed_age > 24 * 7:
        warns.append("economic calendar is %.0f days old" % (feed_age / 24))
    if events is None:
        evs, _ = E.load_all()
    else:
        evs = events
    end = store.parse_iso(o["flat_by"]) if o.get("flat_by") else now + _dt.timedelta(hours=8)
    for e in E.affecting(spec, evs, tuple(lim.get("news_impacts", ["High"]))):
        et = store.parse_iso(e["t"])
        if now < et <= end and e is not ev:
            warns.append("%s %s at %s falls while this trade may be open" % (e["country"], e["title"],
                         store.fmt_t(et, config.get("display_tz", "UTC"), True)))
            break

    wc = (spec.get("session") or {}).get("weekend_cutoff")
    if wc and spec["class"] in ("fx", "cfd"):
        loc = tz.to_local(now, wc["tz"])
        day = DAYS.index(wc["day"])
        cut = _dt.datetime.combine(loc.date() - _dt.timedelta(days=(loc.weekday() - day) % 7), tz.hhmm(wc["time"]))
        if cut - _dt.timedelta(hours=1) <= loc <= cut + _dt.timedelta(hours=50):
            fails.append("too close to the weekend close (%s %s %s): no new trades into the weekend gap" % (wc["day"], wc["time"], wc["tz"]))

    if o.get("margin_est") is not None:
        cap = bal * float(lim.get("max_margin_pct", 100)) / 100.0
        if o["margin_est"] > cap:
            fails.append("margin about %s is over %s%% of your balance" % (store.money(o["margin_est"], ccy), lim.get("max_margin_pct")))
    elif spec["class"] == "future":
        warns.append("no margin figure for %s; check your broker's margin before sending" % spec["symbol"])

    if config.get("paper", True):
        if not o.get("paper"):
            fails.append("config says paper trading but the order is marked live")
        if o["broker"] == "ninjatrader" and not str(o.get("account", "")).lower().startswith("sim"):
            fails.append("paper mode: NinjaTrader account %r is not a Sim account" % o.get("account"))
    if o["broker"] != "signals" and not o.get("broker_symbol"):
        fails.append("no %s symbol for %s" % (o["broker"], spec["symbol"]))

    open_same = [p for p in L.positions().values() if p["symbol"] == o["symbol"] and p["status"] in ("sent", "open") and p.get("kind") == "open"]
    if open_same and not lim.get("allow_stacking"):
        fails.append("already have an open %s trade (%s)" % (o["symbol"], open_same[0]["order_id"]))

    risk = abs(o["entry_ref"] - o["stop"])
    if price is not None:
        drift = (price - o["entry_ref"]) if o["side"] == "long" else (o["entry_ref"] - price)
        if abs(drift) > float(lim.get("max_entry_drift_r", 0.25)) * risk:
            fails.append("price %s has moved %.2fR from the planned entry %s" % (I.fmt_price(price, spec), drift / risk, o["display"]["entry"]))
        if (o["side"] == "long" and price <= o["stop"]) or (o["side"] == "short" and price >= o["stop"]):
            fails.append("price is already through the stop")
    else:
        warns.append("no live price given (--price); drift from the planned entry not checked")
    if spread is not None and lim.get("max_spread_ticks") is not None and spread > lim["max_spread_ticks"]:
        fails.append("spread %g ticks is over your %g limit" % (spread, lim["max_spread_ticks"]))
    return fails, warns


def check_close(o):
    pos = L.positions().get(o.get("close_of"))
    if not pos or pos["status"] not in ("open", "sent"):
        return ["no open trade %s to close" % o.get("close_of")], []
    if o.get("qty") and pos["qty_open"] and o["qty"] > pos["qty_open"] + 1e-9:
        return ["closing %g but only %g is open" % (o["qty"], pos["qty_open"])], []
    if O.fingerprint(o) != o.get("fingerprint"):
        return ["order was edited after it was built (fingerprint mismatch)"], []
    return [], []


def main(argv=None):
    cli_setup()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--price", type=float, help="current price, to check drift from the plan")
    ap.add_argument("--spread", type=float, help="current spread in ticks")
    ap.add_argument("--now")
    args = ap.parse_args(argv)
    config = store.load_config()
    now = store.now_utc(args.now, config.get("display_tz", "UTC"))
    orders = O.load()["orders"]
    if not orders:
        print("No orders. Run size.py --write first.")
        return 1
    state = store.read_json(store.path("state", "risk.json"), {"verdicts": {}})
    blocked = 0
    for i, o in enumerate(orders, 1):
        if o["kind"] == "close":
            fails, warns = check_close(o)
        else:
            fails, warns = check_open(o, I.get(o["symbol"]), config, now, args.price, args.spread)
        verdict = "BLOCK" if fails else "PASS"
        blocked += bool(fails)
        state["verdicts"][o["fingerprint"]] = {"order_id": o["id"], "verdict": verdict, "reasons": fails,
                                               "warnings": warns, "checked": store.iso(now)}
        print("ORDER %d %s %s %s %g %s: %s" % (i, o["id"], o["kind"].upper(), o["side"].upper(), o["qty"], o["symbol"], verdict))
        for f in fails:
            print("  BLOCK: " + f)
        for w in warns:
            print("  note:  " + w)
    store.write_json(store.path("state", "risk.json"), state)
    return 2 if blocked else 0


if __name__ == "__main__":
    sys.exit(activity.run("check", main))
