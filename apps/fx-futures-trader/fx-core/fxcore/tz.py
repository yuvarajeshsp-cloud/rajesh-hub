"""Time zones without third-party packages.

zoneinfo is used when the system has the zone data (Linux, macOS). Windows
Python has no zone database unless `tzdata` is installed, so the zones these
markets need are also built in here with their daylight-saving rules:

  America/New_York, America/Chicago  second Sunday of March 02:00 local
                                     to first Sunday of November 02:00 local
  Europe/London                      last Sunday of March 01:00 UTC
                                     to last Sunday of October 01:00 UTC
  Asia/Kolkata (+05:30), Asia/Tokyo (+09:00), UTC: no daylight saving
"""

import datetime as _dt

UTC = _dt.timezone.utc

_FIXED = {"UTC": 0, "Etc/UTC": 0, "Asia/Kolkata": 330, "Asia/Calcutta": 330, "Asia/Tokyo": 540}
_US = {"America/New_York": -300, "America/Chicago": -360}
_BUILTIN = set(_FIXED) | set(_US) | {"Europe/London"}


def _nth_sunday(year, month, n):
    d = _dt.date(year, month, 1)
    d += _dt.timedelta(days=(6 - d.weekday()) % 7)
    return d + _dt.timedelta(weeks=n - 1)


def _last_sunday(year, month):
    nxt = _dt.date(year + (month == 12), month % 12 + 1, 1)
    d = nxt - _dt.timedelta(days=1)
    return d - _dt.timedelta(days=(d.weekday() + 1) % 7)


def _offset_minutes(zone, utc_dt):
    """Offset from UTC, in minutes, for `zone` at the UTC instant `utc_dt`."""
    if zone in _FIXED:
        return _FIXED[zone]
    y = utc_dt.year
    if zone in _US:
        std = _US[zone]
        # 02:00 local standard time -> UTC; 02:00 local daylight time -> UTC
        start = _dt.datetime.combine(_nth_sunday(y, 3, 2), _dt.time(2)) - _dt.timedelta(minutes=std)
        end = _dt.datetime.combine(_nth_sunday(y, 11, 1), _dt.time(2)) - _dt.timedelta(minutes=std + 60)
        naive = utc_dt.replace(tzinfo=None)
        return std + 60 if start <= naive < end else std
    if zone == "Europe/London":
        start = _dt.datetime.combine(_last_sunday(y, 3), _dt.time(1))
        end = _dt.datetime.combine(_last_sunday(y, 10), _dt.time(1))
        naive = utc_dt.replace(tzinfo=None)
        return 60 if start <= naive < end else 0
    raise KeyError(zone)


def _zoneinfo(zone):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(zone)
    except Exception:
        return None


def to_local(utc_dt, zone):
    """UTC-aware datetime -> naive local wall-clock datetime in `zone`."""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=UTC)
    utc_dt = utc_dt.astimezone(UTC)
    if zone in _BUILTIN:
        return (utc_dt + _dt.timedelta(minutes=_offset_minutes(zone, utc_dt))).replace(tzinfo=None)
    zi = _zoneinfo(zone)
    if zi is None:
        raise ValueError("unknown time zone %r (install tzdata or use a built-in zone)" % zone)
    return utc_dt.astimezone(zi).replace(tzinfo=None)


def to_utc(local_naive, zone):
    """Naive local wall-clock datetime in `zone` -> UTC-aware datetime.

    In the skipped hour of a spring-forward day the standard offset is used;
    in the repeated hour of a fall-back day the first (daylight) one is used.
    """
    if zone in _BUILTIN:
        # Try both candidate offsets; keep the one that round-trips.
        cands = []
        for guess in {_offset_minutes(zone, local_naive.replace(tzinfo=UTC) - _dt.timedelta(hours=h)) for h in (-14, 0, 14)}:
            u = (local_naive - _dt.timedelta(minutes=guess)).replace(tzinfo=UTC)
            if to_local(u, zone) == local_naive:
                cands.append(u)
        if cands:
            return min(cands)
        off = _offset_minutes(zone, local_naive.replace(tzinfo=UTC))
        return (local_naive - _dt.timedelta(minutes=off)).replace(tzinfo=UTC)
    zi = _zoneinfo(zone)
    if zi is None:
        raise ValueError("unknown time zone %r (install tzdata or use a built-in zone)" % zone)
    return local_naive.replace(tzinfo=zi).astimezone(UTC)


def epoch(dt):
    if dt.tzinfo is None:
        raise ValueError("naive datetime")
    return int(dt.timestamp())


def from_epoch(ts):
    return _dt.datetime.fromtimestamp(int(ts), UTC)


def parse_local(text, zone):
    """'2026-10-19 10:15' (or with seconds, or ISO with offset) -> UTC-aware."""
    text = text.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return to_utc(_dt.datetime.strptime(text, fmt), zone)
        except ValueError:
            pass
    dt = _dt.datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return to_utc(dt, zone)
    return dt.astimezone(UTC)


def hhmm(text):
    h, m = text.split(":")
    return _dt.time(int(h), int(m))
