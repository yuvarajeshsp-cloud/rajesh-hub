"""The trade log (trader/state/broker.json): approvals, sends, fills, closes.

trader-risk reads it for the daily loss limit and the trades-per-day count;
trader-broker writes it.
"""

from . import store, tz

LOG = ("state", "broker.json")


def load():
    return store.read_json(store.path(*LOG), {"entries": []})


def append(entry, now=None):
    data = load()
    e = dict(entry)
    e.setdefault("ts", store.iso(now or store.now_utc()))
    data["entries"].append(e)
    store.write_json(store.path(*LOG), data)
    return e


def account_day(t, config):
    return tz.to_local(t, config.get("display_tz") or "UTC").date()


def entries_today(config, now):
    day = account_day(now, config)
    return [e for e in load()["entries"] if account_day(store.parse_iso(e["ts"]), config) == day]


def positions(entries=None):
    """order_id -> {symbol, side, qty_open, max_loss, filled_qty, avg_price, pnl, status}"""
    entries = load()["entries"] if entries is None else entries
    pos = {}
    for e in entries:
        oid = e.get("order_id")
        if not oid:
            continue
        p = pos.setdefault(oid, {"order_id": oid, "symbol": e.get("symbol"), "side": e.get("side"), "qty_open": 0.0,
                                 "filled_qty": 0.0, "avg_price": None, "pnl": 0.0, "status": "proposed",
                                 "max_loss": e.get("max_loss"), "kind": e.get("order_kind", "open")})
        k = e["kind"]
        if e.get("order_kind"):
            p["kind"] = e["order_kind"]
        if k == "sent":
            p["status"] = "sent"
            p["max_loss"] = e.get("max_loss", p["max_loss"])
            p["sent_ts"] = e["ts"]
        elif k in ("placed", "filled"):
            q = float(e.get("filled_qty") or e.get("qty") or 0)
            if q:
                p["filled_qty"] += q
                p["qty_open"] += q
                p["avg_price"] = e.get("filled_price", p["avg_price"])
            p["status"] = "open" if p["qty_open"] > 1e-9 else p["status"]
        elif k in ("closed", "closed_leg"):
            q = float(e.get("qty") or p["qty_open"])
            p["qty_open"] = max(0.0, p["qty_open"] - q)
            p["pnl"] += float(e.get("pnl") or 0)
            p["status"] = "open" if p["qty_open"] > 1e-9 else "closed"
        elif k in ("rejected", "denied", "failed", "expired"):
            if p["qty_open"] <= 1e-9:
                p["status"] = k
    return pos


def risk_today(config, now):
    """(realized P&L today, open risk at stops, open trades started today)."""
    today = entries_today(config, now)
    pos_all = positions()
    realized = sum(float(e.get("pnl") or 0) for e in today if e["kind"] in ("closed", "closed_leg"))
    open_risk = sum(float(p.get("max_loss") or 0) for p in pos_all.values()
                    if p["status"] in ("sent", "open") and p.get("kind") == "open")
    started = sorted({e["order_id"] for e in today if e["kind"] == "sent" and e.get("order_kind", "open") == "open"})
    return realized, open_risk, started
