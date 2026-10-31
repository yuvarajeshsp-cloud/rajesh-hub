"""Execution adapters. None of them talks to a broker over the network:

  signals      prints the ticket; you place it yourself (MCX/NSE, any broker)
  mt5          drops a ticket file for TicketExecutorEA.mq5 (rajesh-hub
               packages/trading/mt5), which re-checks it, asks on screen and trades
  ninjatrader  writes NinjaTrader 8 ATI order-instruction files (oif*.txt) and
               reads its outgoing order-state files
"""

import os
import time
import uuid

from . import instruments as I
from . import store


# ---------------------------------------------------------------- MT5

def mt5_root(config):
    c = config["brokers"]["mt5"]
    base = c.get("common_files") or os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                                                    "MetaQuotes", "Terminal", "Common", "Files")
    return os.path.join(base, *c.get("folder", "RajeshHub\\tickets").replace("/", "\\").split("\\"))


def _flat_json(d):
    """One flat object, numbers unquoted, which is what the EA's reader expects."""
    parts = []
    for k, v in d.items():
        if isinstance(v, bool):
            v = int(v)
        if isinstance(v, (int, float)):
            parts.append('"%s":%s' % (k, repr(v) if isinstance(v, float) else v))
        else:
            parts.append('"%s":"%s"' % (k, str(v).replace('"', "'")))
    return "{" + ",".join(parts) + "}"


def _atomic_text(folder, name, text):
    os.makedirs(folder, exist_ok=True)
    tmp = os.path.join(folder, ".tmp_" + uuid.uuid4().hex[:8])
    with open(tmp, "w", encoding="ascii", errors="replace", newline="") as f:
        f.write(text)
    final = os.path.join(folder, name)
    os.replace(tmp, final)
    return final


def mt5_ticket(o, config, now, ttl_sec=120):
    c = config["brokers"]["mt5"]
    t = int(now.timestamp())
    d = {"action": "OPEN" if o["kind"] == "open" else "CLOSE", "ticket_id": o["id"], "fingerprint": o["fingerprint"],
         "symbol": o["broker_symbol"], "require_demo": bool(config.get("paper", True)),
         "created_utc": t, "expires_utc": t + ttl_sec, "magic": int(c.get("magic", 20261031))}
    if o["kind"] == "open":
        d.update({"dir": "BUY" if o["side"] == "long" else "SELL", "stop": float(o["stop"]),
                  "legs_total": len(o["legs"]), "be_after_tp1": bool(o["be_after_tp1"]),
                  "flat_by_utc": int(store.parse_iso(o["flat_by"]).timestamp()) if o.get("flat_by") else 0,
                  "max_loss": float(o["max_loss"]), "account_ccy": o["account_ccy"],
                  "slippage": int(c.get("slippage_points", 30)), "entry_ref": float(o["entry_ref"])})
        for i, leg in enumerate(o["legs"], 1):
            d["leg%d_qty" % i] = float(leg["qty"])
            d["leg%d_tp" % i] = float(leg["tp"])
    else:
        d["close_of"] = o["close_of"]
    return d


def mt5_send(o, config, now):
    d = mt5_ticket(o, config, now)
    folder = os.path.join(mt5_root(config), "pending")
    name = "%d_%s.json" % (int(now.timestamp() * 1000), o["id"])
    return _atomic_text(folder, name, _flat_json(d)), d


def _parse_flat(text):
    import json
    try:
        return json.loads(text)
    except ValueError:
        return {}


def mt5_results(config):
    folder = os.path.join(mt5_root(config), "results")
    out = {}
    if not os.path.isdir(folder):
        return out
    for n in sorted(os.listdir(folder)):
        if n.endswith(".json"):
            with open(os.path.join(folder, n), "r", encoding="utf-8", errors="replace") as f:
                d = _parse_flat(f.read().strip("\x00﻿ \r\n"))
            if d.get("ticket_id"):
                out[d["ticket_id"]] = d
    return out


# ---------------------------------------------------------------- NinjaTrader 8 ATI

def nt_dirs(config):
    c = config["brokers"]["ninjatrader"]
    base = os.path.join(os.path.expanduser("~"), "Documents", "NinjaTrader 8")
    return c.get("incoming") or os.path.join(base, "incoming"), c.get("outgoing") or os.path.join(base, "outgoing")


def _p(x):
    return ("%.10f" % x).rstrip("0").rstrip(".")


def place(acct, inst, action, qty, otype, limit=0, stop=0, tif="DAY", oco="", oid="", strategy="", sid=""):
    return ";".join(["PLACE", acct, inst, action, _p(qty), otype, _p(limit), _p(stop), tif, oco, oid, strategy, sid])


def nt_entry_lines(o, config):
    c = config["brokers"]["ninjatrader"]
    action = "BUY" if o["side"] == "long" else "SELL"
    if c.get("mode") == "atm":
        name = c.get("atm_template")
        return [place(o["account"], o["broker_symbol"], action, o["qty"], "MARKET", strategy=name, sid=o["id"] + "A")]
    return [place(o["account"], o["broker_symbol"], action, o["qty"], "MARKET", oid=o["id"] + "E")]


def nt_protect_lines(o):
    """One stop + one target per leg, each pair one-cancels-other."""
    out = []
    exit_action = "SELL" if o["side"] == "long" else "BUY"
    for i, leg in enumerate(o["legs"], 1):
        oco = "%sO%d" % (o["id"], i)
        out.append(place(o["account"], o["broker_symbol"], exit_action, leg["qty"], "STOPMARKET", 0, o["stop"], "DAY", oco, "%sS%d" % (o["id"], i)))
        out.append(place(o["account"], o["broker_symbol"], exit_action, leg["qty"], "LIMIT", leg["tp"], 0, "DAY", oco, "%sP%d" % (o["id"], i)))
    return out


def nt_breakeven_lines(o, entry_price, spec):
    out = []
    be = I.round_tick(entry_price, spec)
    for i, leg in enumerate(o["legs"][1:], 2):
        out.append(";".join(["CHANGE", "", "", "", _p(leg["qty"]), "", "0", _p(be), "", "", "%sS%d" % (o["id"], i), "", ""]))
    return out


def nt_close_lines(o, opened):
    c_lines = ["CLOSEPOSITION;%s;%s;;;;;;;;;;" % (opened["account"], opened["broker_symbol"])]
    if opened.get("atm"):
        c_lines = ["CLOSESTRATEGY;;;;;;;;;;;;%sA" % opened["order_id"]]
    for i in range(1, len(opened.get("legs", [])) + 1):
        for k in ("S", "P"):
            c_lines.append("CANCEL;;;;;;;;;;%s%s%d;;" % (opened["order_id"], k, i))
    return c_lines


def nt_write(lines, config, tag):
    incoming, _ = nt_dirs(config)
    name = "oif%s_%s.txt" % (int(time.time() * 1000), tag)
    return _atomic_text(incoming, name, "\r\n".join(lines) + "\r\n")


def nt_order_state(config, order_id):
    """(state, filled_qty, avg_price) from outgoing/<order id>.txt, or None."""
    _, outgoing = nt_dirs(config)
    p = os.path.join(outgoing, order_id + ".txt")
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        parts = f.read().strip().split(";")
    try:
        return parts[0].strip().upper(), float(parts[1] or 0), float(parts[2] or 0)
    except (IndexError, ValueError):
        return parts[0].strip().upper() if parts else "", 0.0, 0.0


def atm_matches(o, spec, config):
    c = config["brokers"]["ninjatrader"]
    name = c.get("atm_template")
    tmpl = (c.get("atm_templates") or {}).get(name or "")
    if not name or not tmpl:
        return False, "ATM mode needs brokers.ninjatrader.atm_template and its stop/targets in atm_templates"
    stop_ticks = round(I.ticks(o["entry_ref"] - o["stop"], spec))
    tgt = [round(I.ticks(l["tp"] - o["entry_ref"], spec)) for l in o["legs"]]
    qtys = [int(l["qty"]) for l in o["legs"]]
    have = [int(x) for x in tmpl.get("target_ticks", [])]
    if abs(stop_ticks - int(tmpl.get("stop_ticks", -1))) > 1:
        return False, "ATM template %r stop is %s ticks, this plan needs %d" % (name, tmpl.get("stop_ticks"), stop_ticks)
    if len(have) != len(tgt) or any(abs(a - b) > 1 for a, b in zip(have, tgt)):
        return False, "ATM template %r targets %s ticks, this plan needs %s" % (name, tmpl.get("target_ticks"), tgt)
    if tmpl.get("qty") and [int(x) for x in tmpl["qty"]] != qtys:
        return False, "ATM template %r quantities %s, this order needs %s" % (name, tmpl["qty"], qtys)
    return True, name
