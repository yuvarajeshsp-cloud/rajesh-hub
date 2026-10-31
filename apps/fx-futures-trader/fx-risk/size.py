#!/usr/bin/env python3
"""Position sizing: lots (forex/CFD) or contracts (futures) from your max loss
per trade, split across the plan's targets.

  size.py                                  # trader/plan.json -> trader/orders.json (prints only)
  size.py --write
  size.py --balance 5000 --risk-pct 0.5 --broker mt5 --write
"""

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fx-core"))

from fxcore import activity, cli_setup, instruments as I, orders as O, store  # noqa: E402


def allocate(qty, step, weights):
    """Split qty into len(weights) legs on the qty step; legs of zero are dropped later."""
    units = int(round(qty / step))
    raw = [units * w for w in weights]
    legs = [int(math.floor(x + 1e-9)) for x in raw]
    left = units - sum(legs)
    order = sorted(range(len(weights)), key=lambda i: -(raw[i] - legs[i]))
    for i in order[:left]:
        legs[i] += 1
    return [round(u * step, 8) for u in legs]


def size(pl, spec, config, balance=None, risk_pct=None, risk_money=None, broker=None):
    acct = config["account"]
    ccy = acct["ccy"].upper()
    bal = float(balance if balance is not None else acct["balance"])
    if risk_money is None and risk_pct is None:
        risk_money = acct.get("risk_per_trade_money")
        risk_pct = acct.get("risk_per_trade_pct")
    target = float(risk_money) if risk_money else bal * float(risk_pct) / 100.0
    unit_loss_native = I.loss_per_unit(pl["entry"], pl["stop"], spec)
    unit_loss = store.convert(unit_loss_native, spec["value_ccy"], ccy, config.get("rates"))
    step, mn, mx = float(spec["qty_step"]), float(spec["min_qty"]), float(spec["max_qty"])
    raw = target / unit_loss
    qty = math.floor(raw / step + 1e-9) * step
    qty = round(min(qty, mx), 8)
    if qty < mn - 1e-12:
        raise ValueError("even the minimum %g %s loses %s at the stop, more than your %s risk. Use a smaller "
                         "instrument (micro future / mini contract), a tighter stop or a bigger risk." % (
                             mn, spec["unit"], store.money(mn * unit_loss, ccy), store.money(target, ccy)))
    weights = [t["weight"] for t in pl["targets"]]
    leg_qty = allocate(qty, step, weights)
    legs = []
    for t, q in zip(pl["targets"], leg_qty):
        if q > 1e-12:
            legs.append({"qty": q, "tp": t["price"], "r": t["r"]})
    dropped = len(pl["targets"]) - len(legs)
    eff_rr = sum(l["qty"] * l["r"] for l in legs) / qty
    max_loss = qty * unit_loss
    broker = broker or config["broker"]
    bsym = None
    account = None
    if broker != "signals":
        bsym = I.broker_symbol(spec, broker, config)
        if not bsym:
            hint = ("set brokers.ninjatrader.contract_months.%s (e.g. \"12-26\") in trader/config.json" % spec["symbol"]
                    if broker == "ninjatrader" and spec.get("brokers", {}).get("ninjatrader") else
                    "%s cannot trade %s here; use --broker signals" % (broker, spec["symbol"]))
            raise ValueError("no %s symbol for %s: %s" % (broker, spec["symbol"], hint))
        account = config["brokers"]["ninjatrader"]["account"] if broker == "ninjatrader" else "mt5"
    margin = None
    m = spec.get("margin") or {}
    if spec["class"] in ("fx", "cfd") and m.get("leverage"):
        notional = qty * spec.get("contract_size", 1) * pl["entry"]
        quote = spec["value_ccy"]
        if spec["class"] == "fx" and spec["symbol"][:3] in ("USD",) and quote != "USD":
            notional = qty * spec["contract_size"]       # USDxxx: notional is in USD
            quote = "USD"
        margin = store.convert(notional, quote, ccy, config.get("rates")) / float(m["leverage"])
    elif m.get("per_contract"):
        margin = store.convert(qty * float(m["per_contract"]), spec["value_ccy"], ccy, config.get("rates"))
    p = lambda x: I.fmt_price(x, spec)
    why = "%s %s: %g %s, bound by your %s risk (%g x %s = %s at the stop)" % (
        pl["rule"]["setup"], spec["symbol"], qty, spec["unit"] + ("s" if qty != 1 else ""), store.money(target, ccy),
        qty, store.money(unit_loss, ccy), store.money(max_loss, ccy))
    order = {
        "kind": "open", "symbol": spec["symbol"], "class": spec["class"], "unit": spec["unit"],
        "broker": broker, "broker_symbol": bsym, "account": account, "paper": bool(config.get("paper", True)),
        "side": pl["side"], "type": "market", "qty": qty, "legs": legs, "stop": pl["stop"],
        "entry_ref": pl["entry"], "risk_ticks": pl["risk_ticks"], "risk": pl["risk"],
        "loss_per_unit": round(unit_loss, 4), "max_loss": round(max_loss, 2), "risk_target": round(target, 2),
        "account_ccy": ccy, "value_ccy": spec["value_ccy"], "rr": round(eff_rr, 3),
        "be_after_tp1": pl["be_after_tp1"], "signal_t": pl["signal_t"], "valid_until": pl["valid_until"],
        "flat_by": pl.get("flat_by"), "margin_est": round(margin, 2) if margin is not None else None,
        "spec_verified": bool(spec.get("verified")), "why": why,
        "display": {"entry": p(pl["entry"]), "stop": p(pl["stop"]), "tps": [p(l["tp"]) for l in legs]},
    }
    if dropped:
        order["note"] = "%d target(s) dropped: %g %s cannot be split %d ways" % (dropped, qty, spec["unit"], len(pl["targets"]))
    return order


def main(argv=None):
    cli_setup()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan")
    ap.add_argument("--balance", type=float)
    ap.add_argument("--risk-pct", type=float)
    ap.add_argument("--risk-money", type=float)
    ap.add_argument("--broker", choices=["signals", "mt5", "ninjatrader"])
    ap.add_argument("--now")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    config = store.load_config()
    pl = store.read_json(args.plan or store.path("plan.json"))
    if not pl:
        print("No plan. Run fx-entry-exit: plan.py make SYMBOL --write")
        return 1
    spec = I.get(pl["symbol"])
    try:
        o = size(pl, spec, config, args.balance, args.risk_pct, args.risk_money, args.broker)
    except (ValueError, KeyError) as e:
        print("NO ORDER:", e)
        return 2
    o = O.finalize(o, store.now_utc(args.now, config.get("display_tz", "UTC")))
    ccy = o["account_ccy"]
    print("ORDER %s  %s %g %s %s  (%s, %s)" % (o["id"], o["side"].upper(), o["qty"], o["symbol"], o["unit"] + ("s" if o["qty"] != 1 else ""),
          o["broker"], "PAPER/DEMO" if o["paper"] else "LIVE"))
    print("  entry about %s market, stop %s" % (o["display"]["entry"], o["display"]["stop"]))
    for i, (l, tp) in enumerate(zip(o["legs"], o["display"]["tps"]), 1):
        print("  leg %d: %g at TP%d %s (%gR)" % (i, l["qty"], i, tp, l["r"]))
    print("  max loss at the stop %s (target %s); reward/risk %.2f" % (store.money(o["max_loss"], ccy), store.money(o["risk_target"], ccy), o["rr"]))
    if o["margin_est"] is not None:
        print("  margin about %s" % store.money(o["margin_est"], ccy))
    if o.get("note"):
        print("  note:", o["note"])
    if not o["spec_verified"]:
        print("  spec for %s is marked VERIFY: check tick size/value with your broker (see fx-risk SKILL.md)" % o["symbol"])
    if args.write:
        store.write_json(store.path("orders.json"), {"created": o["created"], "orders": [o]})
        print("wrote", store.path("orders.json"))
    return 0


if __name__ == "__main__":
    sys.exit(activity.run("size", main))
