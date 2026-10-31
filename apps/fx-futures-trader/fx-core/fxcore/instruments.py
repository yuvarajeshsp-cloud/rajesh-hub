"""Instrument specs: defaults in instruments.json, overridden by trader/instruments.json."""

import math

from . import store

_ALIASES = {"GOLD": "XAUUSD", "SILVER": "XAGUSD", "BANK_NIFTY": "BANKNIFTY", "NIFTY50": "NIFTY"}


def _resolve(name, table, templates, seen=()):
    spec = dict(table[name]) if name in table else dict(templates[name])
    base = spec.pop("_base", None)
    if base:
        if base in seen:
            raise ValueError("template loop at %s" % base)
        spec = store.deep_merge(_resolve(base, {}, templates, seen + (base,)), spec)
    return spec


def load_all():
    default = store.read_json(store.HERE + "/instruments.json")
    over = store.read_json(store.path("instruments.json"), {}) or {}
    templates = store.deep_merge(default["templates"], over.get("templates", {}))
    table = store.deep_merge(default["instruments"], over.get("instruments", {}))
    out = {}
    for name in table:
        s = _resolve(name, table, templates)
        s["symbol"] = name
        s.setdefault("value_ccy", "USD")
        s.setdefault("currencies", [])
        s.setdefault("brokers", {})
        s.setdefault("verified", False)
        s.setdefault("unit", "contract" if s.get("class") == "future" else "lot")
        out[name] = s
    return out


def get(symbol, specs=None):
    specs = specs or load_all()
    key = symbol.upper().replace("/", "")
    key = _ALIASES.get(key, key)
    if key not in specs and "MCX_" + key in specs:
        key = "MCX_" + key
    if key not in specs:
        raise KeyError("unknown instrument %r. Known: %s. Add it to trader/instruments.json." % (symbol, ", ".join(sorted(specs))))
    return specs[key]


def round_tick(price, spec, mode="nearest"):
    t = spec["tick_size"]
    n = price / t
    n = math.floor(n + 1e-9) if mode == "down" else math.ceil(n - 1e-9) if mode == "up" else round(n)
    return round(n * t, tick_decimals(spec))


def tick_decimals(spec):
    t = spec["tick_size"]
    return 0 if t >= 1 and float(t).is_integer() else len(("%.10f" % t).rstrip("0").split(".")[1])


def ticks(distance, spec):
    return abs(distance) / spec["tick_size"]


def loss_per_unit(entry, stop, spec):
    """Money lost by ONE lot/contract from entry to stop, in spec value_ccy."""
    return round(ticks(entry - stop, spec), 6) * spec["tick_value"]


def broker_symbol(spec, broker, config):
    tmpl = spec.get("brokers", {}).get(broker)
    if not tmpl:
        return None
    if "{month}" in tmpl:
        months = config["brokers"]["ninjatrader"].get("contract_months", {})
        m = months.get(spec["symbol"]) or months.get("default")
        if not m:
            return None
        tmpl = tmpl.replace("{month}", m)
    return tmpl


def fmt_price(price, spec):
    return ("%." + str(tick_decimals(spec)) + "f") % price
