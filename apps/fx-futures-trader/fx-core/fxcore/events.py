"""Economic calendar: the free ForexFactory weekly feed plus your own events
(RBI, Union Budget, MCX/NSE expiry...), and the news blackout check."""

import datetime as _dt
import json
import urllib.request

from . import store, tz

FEED = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
UA = "Mozilla/5.0 (fx-futures-trader; personal use)"


def parse_feed(doc):
    out = []
    for e in doc:
        try:
            when = _dt.datetime.fromisoformat(e["date"]).astimezone(tz.UTC)
        except (KeyError, ValueError):
            continue
        out.append({"title": e.get("title", ""), "country": (e.get("country") or "").upper(),
                    "t": store.iso(when), "impact": e.get("impact", ""),
                    "forecast": e.get("forecast", ""), "previous": e.get("previous", ""), "source": "forexfactory"})
    return out


def fetch(opener=None):
    req = urllib.request.Request(FEED, headers={"User-Agent": UA})
    raw = (opener or urllib.request.urlopen)(req, timeout=30).read()
    return parse_feed(json.loads(raw.decode("utf-8")))


def save(events):
    old = store.read_json(store.path("events.json"), {"events": []})["events"]
    key = lambda e: (e["t"], e["country"], e["title"])
    merged = {key(e): e for e in old}
    merged.update({key(e): e for e in events})
    data = {"updated": store.iso(store.now_utc()), "events": sorted(merged.values(), key=lambda e: e["t"])}
    store.write_json(store.path("events.json"), data)
    return data


def load_all():
    feed = store.read_json(store.path("events.json"), {"events": []})
    manual = store.read_json(store.path("events.manual.json"), [])
    evs = list(feed.get("events", []))
    for e in manual:
        e = dict(e)
        if "t" not in e:
            e["t"] = store.iso(tz.parse_local(e["at"], e.get("tz", "Asia/Kolkata")))
        e["country"] = e.get("country", "").upper()
        e.setdefault("impact", "High")
        e.setdefault("source", "manual")
        evs.append(e)
    return sorted(evs, key=lambda e: e["t"]), feed.get("updated")


def affecting(spec, events, impacts=("High",)):
    ccys = set(c.upper() for c in spec.get("currencies", []))
    syms = {spec["symbol"].upper()}
    return [e for e in events if e.get("impact") in impacts and
            (e["country"] in ccys or e["country"] in syms or e["country"] == "ALL")]


def blackout(spec, t, config, events=None):
    """(clear, event, minutes_away, feed_age_hours) for an instant `t` (aware UTC)."""
    lim = config["limits"]
    before, after = lim.get("news_blackout_before_min", 15), lim.get("news_blackout_after_min", 15)
    if events is None:
        events, updated = load_all()
    else:
        updated = None
    age = None
    if updated:
        age = (t - store.parse_iso(updated)).total_seconds() / 3600
    for e in affecting(spec, events, tuple(lim.get("news_impacts", ["High"]))):
        et = store.parse_iso(e["t"])
        mins = (et - t).total_seconds() / 60
        if -after <= mins <= before:
            return False, e, mins, age
    return True, None, None, age
