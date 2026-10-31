"""Order identity: every order carries a fingerprint of the fields that matter,
so a risk PASS and your yes apply to that exact order and nothing else."""

from . import store

KEYS = ("kind", "symbol", "broker", "broker_symbol", "account", "paper", "side", "type", "qty", "legs", "stop",
        "be_after_tp1", "flat_by", "close_of")


def fingerprint(o):
    return store.fingerprint({k: o.get(k) for k in KEYS})


def finalize(order, now):
    order["created"] = store.iso(now)
    order["fingerprint"] = fingerprint(order)
    order["id"] = "T%s%s" % (now.strftime("%m%d%H%M"), order["fingerprint"][:4].upper())
    return order


def load():
    return store.read_json(store.path("orders.json"), {"orders": []})


def verdicts():
    return store.read_json(store.path("state", "risk.json"), {"verdicts": {}})["verdicts"]
