#!/usr/bin/env python3
"""Order executor: tickets, your yes, and the hand-off to MT5, NinjaTrader or you.

  ticket.py show                               # every ticket, READY or not
  ticket.py approve --index 1 --reply "yes"     # records your yes, word for word
  ticket.py send --index 1                     # only after a recorded yes
  ticket.py sync [--watch 30]                  # read fills/closes back from MT5 / NinjaTrader
  ticket.py fill --index 1 --qty 0.3 --price 2654.4    # signals mode: you placed it yourself
  ticket.py close --order T10310915AB12 --price 2658.4 --qty 0.1   # record an exit
  ticket.py flatten --order T10310915AB12      # builds the close ticket (then risk, yes, send)
  ticket.py log
"""

import argparse
import glob
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fx-core"))

from fxcore import cli_setup, execution as X, instruments as I, ledger as L, orders as O, store  # noqa: E402

RISK_FRESH_MIN = 15
NO_WORDS = {"no", "not", "dont", "don't", "wait", "cancel", "stop", "hold", "maybe", "later", "all", "every", "both", "everything"}


def ready(o, config, now):
    v = O.verdicts().get(o["fingerprint"])
    if not v:
        return False, "NOT READY: run /fx-risk (check.py) for this order"
    age = (now - store.parse_iso(v["checked"])).total_seconds() / 60
    if v["verdict"] != "PASS":
        return False, "BLOCKED by fx-risk: " + "; ".join(v["reasons"])
    if age > RISK_FRESH_MIN:
        return False, "NOT READY: the risk check is %.0f minutes old, run check.py again" % age
    if O.fingerprint(o) != o["fingerprint"]:
        return False, "NOT READY: order changed after the risk check"
    if any(e.get("order_id") == o["id"] and e["kind"] == "sent" for e in L.load()["entries"]):
        return False, "ALREADY SENT"
    return True, "READY: fx-risk PASS, waiting for your yes"


def payload_text(o, config):
    if o["broker"] == "mt5":
        return "MT5 ticket file for TicketExecutorEA: " + X._flat_json(X.mt5_ticket(o, config, store.now_utc()))
    if o["broker"] == "ninjatrader":
        if o["kind"] == "close":
            opened = _opened(o["close_of"])
            return "NinjaTrader OIF:\n    " + "\n    ".join(X.nt_close_lines(o, opened))
        lines = X.nt_entry_lines(o, config)
        if config["brokers"]["ninjatrader"].get("mode") != "atm":
            lines += ["(after the entry fills) " + ln for ln in X.nt_protect_lines(o)]
        return "NinjaTrader OIF:\n    " + "\n    ".join(lines)
    return "signals only: nothing is sent, you place it in your broker"


def render(i, n, o, config, now):
    ok, status = ready(o, config, now)
    acct = "PAPER/DEMO" if o.get("paper") else "LIVE"
    where = {"mt5": "MetaTrader 5", "ninjatrader": "NinjaTrader %s" % o.get("account"), "signals": "you (signals only)"}[o["broker"]]
    lines = ["TICKET %d of %d  %s  %s account, via %s" % (i, n, o["id"], acct, where)]
    if o["kind"] == "close":
        lines.append("  CLOSE %g %s (trade %s) at market" % (o["qty"], o["broker_symbol"] or o["symbol"], o["close_of"]))
    else:
        unit = o["unit"] + ("s" if o["qty"] != 1 else "")
        lines.append("  %s %g %s %s at market (planned %s)" % ("BUY" if o["side"] == "long" else "SELL", o["qty"],
                     o["broker_symbol"] or o["symbol"], unit, o["display"]["entry"]))
        lines.append("  stop-loss %s on every leg" % o["display"]["stop"])
        for k, (leg, tp) in enumerate(zip(o["legs"], o["display"]["tps"]), 1):
            lines.append("  leg %d: %g, take-profit %s (%gR)" % (k, leg["qty"], tp, leg["r"]))
        if o["be_after_tp1"] and len(o["legs"]) > 1:
            lines.append("  after TP1 the other legs' stop moves to the entry price")
        if o.get("flat_by"):
            lines.append("  flat by %s" % store.fmt_t(store.parse_iso(o["flat_by"]), config.get("display_tz", "UTC"), True))
        lines.append("  max loss about %s if the stop fills at %s (it can fill worse in a fast market)" % (
            store.money(o["max_loss"], o["account_ccy"]), o["display"]["stop"]))
        lines.append("  why: " + o["why"])
    lines.append("  " + status)
    lines.append("  " + payload_text(o, config).replace("\n", "\n  "))
    return ok, "\n".join(lines)


def _get(args, orders):
    if not orders:
        raise SystemExit("No orders. Run fx-risk size.py --write first.")
    if args.index is None:
        if len(orders) == 1:
            return 1, orders[0]
        raise SystemExit("Give --index N (1..%d)" % len(orders))
    if not 1 <= args.index <= len(orders):
        raise SystemExit("No ticket %d (have %d)" % (args.index, len(orders)))
    return args.index, orders[args.index - 1]


def is_explicit_yes(reply, o, index, specs):
    words = [w.strip(".'") for w in re.findall(r"[a-z0-9_.']+", reply.lower())]
    words = [w for w in words if w]
    if not words or words[0] != "yes":
        return False, "the reply does not start with 'yes'"
    bad = [w for w in words[1:] if w in NO_WORDS]
    if bad:
        return False, "the reply also says %r; one clear yes per order" % bad[0]
    names = {s.lower() for s in specs} | {"gold", "silver", "nifty", "banknifty"}
    mine = {o["symbol"].lower(), str(o.get("broker_symbol") or "").lower().split(" ")[0]}
    for w in words:
        if w in names and w not in mine and not (w == "gold" and o["symbol"] in ("XAUUSD", "GC", "MGC", "MCX_GOLD", "MCX_GOLDM")):
            return False, "the reply names %s, this ticket is %s" % (w.upper(), o["symbol"])
    allowed = {float(index), float(o["qty"])} | {float(l["qty"]) for l in o.get("legs", [])}
    for k in ("stop", "entry_ref"):
        if o.get(k) is not None:
            allowed.add(round(float(o[k]), 6))
    for l in o.get("legs", []):
        allowed.add(round(float(l["tp"]), 6))
    for w in words:
        try:
            num = float(w.strip("."))
        except ValueError:
            continue
        if not any(abs(num - a) < 1e-9 for a in allowed):
            return False, "the reply mentions %s, which is not on this ticket" % w
    return True, ""


def cmd_show(args):
    config = store.load_config()
    now = store.now_utc(args.now, config.get("display_tz", "UTC"))
    orders = O.load()["orders"]
    if not orders:
        print("No orders. Run fx-risk size.py --write first.")
        return 1
    for i, o in enumerate(orders, 1):
        if args.index and i != args.index:
            continue
        print(render(i, len(orders), o, config, now)[1])
        print()
    return 0


def cmd_approve(args):
    config = store.load_config()
    now = store.now_utc(args.now, config.get("display_tz", "UTC"))
    orders = O.load()["orders"]
    i, o = _get(args, orders)
    ok, status = ready(o, config, now)
    if not ok:
        print("Not recorded: ticket %d is %s" % (i, status))
        return 2
    good, why = is_explicit_yes(args.reply, o, i, I.load_all())
    if not good:
        L.append({"kind": "reply_not_yes", "order_id": o["id"], "fingerprint": o["fingerprint"], "reply": args.reply, "why": why}, now)
        print("Not recorded: %s. Ask again: \"Place ticket %d? Reply yes or no.\"" % (why, i))
        return 2
    L.append({"kind": "approved", "order_id": o["id"], "fingerprint": o["fingerprint"], "reply": args.reply,
              "symbol": o["symbol"], "side": o["side"], "qty": o["qty"], "order_kind": o["kind"]}, now)
    print("Recorded your yes for ticket %d (%s %g %s). Send it within %d minutes: ticket.py send --index %d" % (
        i, o["side"], o["qty"], o["symbol"], config.get("approval_valid_min", 10), i))
    return 0


def _approval(o, config, now):
    for e in reversed(L.load()["entries"]):
        if e.get("order_id") == o["id"] and e["kind"] == "approved" and e.get("fingerprint") == o["fingerprint"]:
            age = (now - store.parse_iso(e["ts"])).total_seconds() / 60
            return e if 0 <= age <= config.get("approval_valid_min", 10) else None
    return None


def _opened(order_id):
    for e in L.load()["entries"]:
        if e.get("order_id") == order_id and e["kind"] == "sent":
            return e
    return None


def cmd_send(args):
    config = store.load_config()
    now = store.now_utc(args.now, config.get("display_tz", "UTC"))
    orders = O.load()["orders"]
    i, o = _get(args, orders)
    ok, status = ready(o, config, now)
    if not ok:
        print("NOT SENT: " + status)
        return 2
    if not _approval(o, config, now):
        print("NOT SENT: no recorded yes for this exact ticket in the last %d minutes. Show it and ask." % config.get("approval_valid_min", 10))
        return 2
    base = {"order_id": o["id"], "fingerprint": o["fingerprint"], "symbol": o["symbol"], "side": o["side"], "qty": o["qty"],
            "max_loss": o.get("max_loss", 0) if o["kind"] == "open" else 0, "order_kind": o["kind"], "broker": o["broker"],
            "broker_symbol": o.get("broker_symbol"), "account": o.get("account"), "legs": o.get("legs", []),
            "entry_ref": o.get("entry_ref"), "stop": o.get("stop"), "be_after_tp1": o.get("be_after_tp1"),
            "close_of": o.get("close_of"), "account_ccy": o.get("account_ccy")}
    if o["broker"] == "mt5":
        path, _ = X.mt5_send(o, config, now)
        L.append(dict(base, kind="sent", file=path), now)
        print("SENT to MT5: %s\nTicketExecutorEA picks it up within 2 seconds, re-checks it and asks you on screen. "
              "It expires in 120 s if the EA is not running. Then: ticket.py sync" % path)
    elif o["broker"] == "ninjatrader":
        if o["kind"] == "close":
            lines = X.nt_close_lines(o, _opened(o["close_of"]) or {})
        else:
            if config["brokers"]["ninjatrader"].get("mode") == "atm":
                good, name = X.atm_matches(o, I.get(o["symbol"]), config)
                if not good:
                    print("NOT SENT: " + name)
                    return 2
                base["atm"] = name
            lines = X.nt_entry_lines(o, config)
        path = X.nt_write(lines, config, o["id"])
        L.append(dict(base, kind="sent", file=path), now)
        print("SENT to NinjaTrader (%s): %s" % (o.get("account"), path))
        if o["kind"] == "open" and not base.get("atm"):
            print("Protection (stop + targets) goes in the moment the entry fills. Waiting up to %d s..." % args.wait)
            deadline = time.time() + args.wait
            while time.time() < deadline:
                if sync_nt(config, now=None, quiet=True):
                    break
                time.sleep(1)
            else:
                print("Entry fill not seen yet. Run ticket.py sync NOW: the position has no stop until it does.")
    else:
        L.append(dict(base, kind="sent", manual=True), now)
        print("Signals only: place this yourself now, then record it: ticket.py fill --order %s --qty %g --price <fill>" % (o["id"], o["qty"]))
    return 0


# ---------------------------------------------------------------- sync

def _logged(order_id, kind, tag=None):
    return any(e.get("order_id") == order_id and e["kind"] == kind and (tag is None or e.get("tag") == tag)
               for e in L.load()["entries"])


def pnl_money(sent, qty, entry, exit_, config):
    spec = I.get(sent["symbol"])
    sign = 1 if sent["side"] == "long" else -1
    native = sign * (exit_ - entry) / spec["tick_size"] * spec["tick_value"] * qty
    return round(store.convert(native, spec["value_ccy"], sent.get("account_ccy") or config["account"]["ccy"], config.get("rates")), 2)


def sync_mt5(config, quiet=False):
    res = X.mt5_results(config)
    done = 0
    for e in [x for x in L.load()["entries"] if x["kind"] == "sent" and x.get("broker") == "mt5"]:
        r = res.get(e["order_id"])
        if not r:
            continue
        st = r.get("status", "")
        oid = e["order_id"]
        if st == "placed" and e.get("order_kind") == "close":
            if not _logged(oid, "done"):
                L.append({"kind": "done", "order_id": oid, "symbol": e["symbol"], "order_kind": "close", "reason": r.get("reason")})
                done += 1
        elif st == "placed" and not _logged(oid, "placed"):
            L.append({"kind": "placed", "order_id": oid, "symbol": e["symbol"], "filled_qty": r.get("filled_qty"),
                      "filled_price": r.get("avg_price"), "broker_ref": r.get("positions"), "order_kind": e.get("order_kind")})
            done += 1
        elif st in ("rejected", "denied", "dryrun", "expired") and not _logged(oid, st):
            L.append({"kind": st if st != "dryrun" else "rejected", "order_id": oid, "symbol": e["symbol"], "reason": r.get("reason")})
            done += 1
        if e.get("order_kind") == "open" and r.get("closed_qty"):
            # The EA reports running totals; log only what is new since the last sync.
            prior = [x for x in L.load()["entries"] if x.get("order_id") == oid and x.get("source") == "mt5"
                     and x["kind"] in ("closed", "closed_leg")]
            dq = float(r["closed_qty"]) - sum(float(x.get("qty") or 0) for x in prior)
            dp = float(r.get("pnl") or 0) - sum(float(x.get("pnl") or 0) for x in prior)
            if dq > 1e-9:
                L.append({"kind": "closed_leg", "order_id": oid, "symbol": e["symbol"], "qty": round(dq, 8),
                          "pnl": round(dp, 2), "source": "mt5"})
                done += 1
        if not quiet and (done or st):
            print("%s %s: %s %s" % (oid, e["symbol"], st, r.get("reason", "")))
    return done


def sync_nt(config, now=None, quiet=False):
    entries = L.load()["entries"]
    acted = 0
    for e in [x for x in entries if x["kind"] == "sent" and x.get("broker") == "ninjatrader" and x.get("order_kind") == "open"]:
        oid = e["order_id"]
        if e.get("atm"):
            st = _nt_position(config, e)
            if st and st[0] in ("LONG", "SHORT") and not _logged(oid, "placed"):
                L.append({"kind": "placed", "order_id": oid, "symbol": e["symbol"], "filled_qty": st[1], "filled_price": st[2]})
                acted += 1
            elif st and st[0] == "FLAT" and _logged(oid, "placed") and not _logged(oid, "closed"):
                L.append({"kind": "closed", "order_id": oid, "symbol": e["symbol"], "qty": e["qty"], "pnl": None,
                          "note": "ATM closed; record the P&L with ticket.py close --order %s --pnl X" % oid})
                acted += 1
            continue
        ent = X.nt_order_state(config, oid + "E")
        if ent and ent[0] in ("REJECTED", "CANCELLED") and not _logged(oid, "rejected"):
            L.append({"kind": "rejected", "order_id": oid, "symbol": e["symbol"], "reason": "NinjaTrader " + ent[0]})
            acted += 1
            continue
        if ent and ent[0] == "FILLED" and not _logged(oid, "placed"):
            L.append({"kind": "placed", "order_id": oid, "symbol": e["symbol"], "filled_qty": ent[1], "filled_price": ent[2]})
            o = dict(e, id=oid)
            X.nt_write(X.nt_protect_lines(o), config, oid + "P")
            L.append({"kind": "protected", "order_id": oid, "symbol": e["symbol"]})
            if not quiet:
                print("%s filled %g at %s; stop and targets placed" % (oid, ent[1], ent[2]))
            acted += 1
        if not _logged(oid, "placed"):
            continue
        fill = next((x for x in L.load()["entries"] if x.get("order_id") == oid and x["kind"] == "placed"), {})
        fill_px = float(fill.get("filled_price") or e["entry_ref"])
        pos_now = L.positions().get(oid, {})
        flat = _nt_position(config, e)
        if flat and flat[0] == "FLAT" and pos_now.get("qty_open", 0) > 1e-9 and _logged(oid, "protected"):
            # Flattened outside our stop/target orders (CLOSEPOSITION, or by hand): close the rest.
            L.append({"kind": "closed", "order_id": oid, "symbol": e["symbol"], "qty": pos_now["qty_open"], "pnl": None,
                      "note": "position flat in NinjaTrader; record the P&L with ticket.py close --order %s --pnl X" % oid})
            if not quiet:
                print("%s is flat in NinjaTrader; record its P&L: ticket.py close --order %s --pnl X" % (oid, oid))
            acted += 1
            continue
        for k, leg in enumerate(e.get("legs", []), 1):
            for kind, tag in (("P", "tp%d" % k), ("S", "sl%d" % k)):
                st = X.nt_order_state(config, "%s%s%d" % (oid, kind, k))
                if st and st[0] == "FILLED" and not _logged(oid, "closed_leg", tag):
                    L.append({"kind": "closed_leg", "order_id": oid, "symbol": e["symbol"], "qty": st[1] or leg["qty"], "tag": tag,
                              "price": st[2], "pnl": pnl_money(e, st[1] or leg["qty"], fill_px, st[2], config)})
                    acted += 1
                    if kind == "P" and k == 1 and e.get("be_after_tp1") and len(e["legs"]) > 1 and not _logged(oid, "breakeven"):
                        X.nt_write(X.nt_breakeven_lines(dict(e, id=oid), fill_px, I.get(e["symbol"])), config, oid + "B")
                        L.append({"kind": "breakeven", "order_id": oid, "symbol": e["symbol"], "price": fill_px})
                        if not quiet:
                            print("%s TP1 filled; stops on the other legs moved to %s" % (oid, fill_px))
    return acted


def _nt_position(config, e):
    _, outgoing = X.nt_dirs(config)
    pat = os.path.join(outgoing, "%s *_%s_Position.txt" % (e["broker_symbol"], e["account"]))
    for p in glob.glob(pat):
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            parts = [x.strip() for x in f.read().strip().split(";")]
        try:
            return parts[0].upper(), float(parts[1] or 0), float(parts[2] or 0)
        except (IndexError, ValueError):
            return parts[0].upper(), 0.0, 0.0
    return None


def cmd_sync(args):
    config = store.load_config()
    while True:
        a = sync_mt5(config) + sync_nt(config)
        pos = [p for p in L.positions().values() if p["status"] in ("sent", "open")]
        for p in pos:
            print("open: %s %s %s %g (P&L so far %s)" % (p["order_id"], p["symbol"], p["side"], p["qty_open"], p["pnl"]))
        if not args.watch:
            print("synced, %d update(s)" % a)
            return 0
        time.sleep(max(5, args.watch))


def cmd_fill(args):
    sent = _opened(args.order)
    if not sent:
        print("No sent trade %s" % args.order)
        return 2
    L.append({"kind": "placed", "order_id": args.order, "symbol": sent["symbol"], "filled_qty": args.qty, "filled_price": args.price, "source": "manual"})
    print("recorded entry fill %g at %s for %s" % (args.qty, args.price, args.order))
    return 0


def cmd_close(args):
    config = store.load_config()
    sent = _opened(args.order)
    if not sent:
        print("No sent trade %s" % args.order)
        return 2
    pos = L.positions().get(args.order, {})
    qty = args.qty or pos.get("qty_open") or sent["qty"]
    if args.pnl is not None:
        pnl = args.pnl
    else:
        if args.price is None:
            print("give --price (exit fill) or --pnl")
            return 2
        entry = float(pos.get("avg_price") or sent["entry_ref"])
        pnl = pnl_money(sent, qty, entry, args.price, config)
    L.append({"kind": "closed_leg" if pos.get("qty_open") and qty < pos["qty_open"] - 1e-9 else "closed", "order_id": args.order,
              "symbol": sent["symbol"], "qty": qty, "price": args.price, "pnl": pnl, "source": "manual"})
    print("recorded exit of %g %s: P&L %s" % (qty, sent["symbol"], store.money(pnl, sent.get("account_ccy") or config["account"]["ccy"])))
    return 0


def cmd_flatten(args):
    config = store.load_config()
    now = store.now_utc(args.now, config.get("display_tz", "UTC"))
    pos = L.positions().get(args.order)
    sent = _opened(args.order)
    if not pos or not sent or pos["status"] not in ("open", "sent"):
        print("No open trade %s" % args.order)
        return 2
    qty = args.qty or pos["qty_open"] or sent["qty"]
    o = {"kind": "close", "close_of": args.order, "symbol": sent["symbol"], "side": "close", "qty": qty,
         "broker": sent["broker"], "broker_symbol": sent.get("broker_symbol"), "account": sent.get("account"),
         "paper": bool(config.get("paper", True)), "type": "market", "legs": [], "stop": None,
         "unit": I.get(sent["symbol"])["unit"], "account_ccy": sent.get("account_ccy")}
    o = O.finalize(o, now)
    store.write_json(store.path("orders.json"), {"created": o["created"], "orders": [o]})
    print("Close ticket %s written for %g %s. Next: check.py, then show it and ask for a yes." % (o["id"], qty, sent["symbol"]))
    return 0


def cmd_log(args):
    config = store.load_config()
    zone = config.get("display_tz", "UTC")
    for e in L.load()["entries"][-args.last:]:
        extra = " ".join("%s=%s" % (k, e[k]) for k in ("qty", "filled_price", "price", "pnl", "reason", "reply") if e.get(k) not in (None, ""))
        print("%s %-14s %-14s %-10s %s" % (store.fmt_t(store.parse_iso(e["ts"]), zone, True), e["kind"], e.get("order_id", ""), e.get("symbol", ""), extra))
    realized, open_risk, started = L.risk_today(config, store.now_utc())
    ccy = config["account"]["ccy"]
    print("\ntoday: %d trade(s), realized %s, open risk at stops %s" % (len(started), store.money(realized, ccy), store.money(open_risk, ccy)))
    return 0


def main(argv=None):
    cli_setup()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show"); s.add_argument("--index", type=int); s.add_argument("--now")
    a = sub.add_parser("approve"); a.add_argument("--index", type=int); a.add_argument("--reply", required=True); a.add_argument("--now")
    se = sub.add_parser("send"); se.add_argument("--index", type=int); se.add_argument("--now"); se.add_argument("--wait", type=int, default=20)
    sy = sub.add_parser("sync"); sy.add_argument("--watch", type=int, default=0)
    f = sub.add_parser("fill"); f.add_argument("--order", required=True); f.add_argument("--qty", type=float, required=True); f.add_argument("--price", type=float, required=True)
    c = sub.add_parser("close"); c.add_argument("--order", required=True); c.add_argument("--qty", type=float); c.add_argument("--price", type=float); c.add_argument("--pnl", type=float)
    fl = sub.add_parser("flatten"); fl.add_argument("--order", required=True); fl.add_argument("--qty", type=float); fl.add_argument("--now")
    lg = sub.add_parser("log"); lg.add_argument("--last", type=int, default=30)
    args = ap.parse_args(argv)
    return {"show": cmd_show, "approve": cmd_approve, "send": cmd_send, "sync": cmd_sync, "fill": cmd_fill,
            "close": cmd_close, "flatten": cmd_flatten, "log": cmd_log}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
