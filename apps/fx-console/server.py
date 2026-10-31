#!/usr/bin/env python3
"""Trading Console server: shows what the fx-futures-trader skills are doing.

  python3 server.py                 # watch ./trader (the folder the skills write to)
  python3 server.py --trader-dir D:\\trading\\trader --port 8765
  python3 server.py --demo          # a self-running pipeline on synthetic data

Open http://127.0.0.1:8765. Standard library only. Binds to 127.0.0.1.

Endpoints
  GET  /api/state    everything the UI shows, from the trader/ files
  GET  /api/events   Server-Sent Events: live activity lines + state changes
  POST /api/run      start a read-only stage (scan, calendar, replay, risk
                     check, sync). The console can NEVER approve, send or
                     flatten an order: that stays in the chat, behind your yes.
"""

import argparse
import datetime as _dt
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.environ.get("FX_PACK_DIR") or os.path.join(os.path.dirname(HERE), "fx-futures-trader")
sys.path.insert(0, os.path.join(PACK, "fx-core"))

from fxcore import activity, events as E, ledger as L, orders as O, store  # noqa: E402

DIST = os.path.join(HERE, "dist")
WATCH = ["config.json", "scan.json", "events.json", "events.manual.json", "plan.json", "replay.json", "orders.json",
         os.path.join("state", "risk.json"), os.path.join("state", "broker.json")]
SYMBOL_RE = re.compile(r"^[A-Za-z0-9_]{2,16}$")

STAGES = [
    {"id": "scan", "label": "Scanner", "skill": "fx-scanner"},
    {"id": "calendar", "label": "Calendar", "skill": "fx-calendar"},
    {"id": "plan", "label": "Entry / Exit", "skill": "fx-entry-exit"},
    {"id": "replay", "label": "Time machine", "skill": "fx-timemachine"},
    {"id": "risk", "label": "Risk gate", "skill": "fx-risk"},
    {"id": "broker", "label": "Broker", "skill": "fx-broker"},
    {"id": "sync", "label": "Sync", "skill": "fx-broker"},
]

DEMO = {"on": False}


def ui_stage(ev):
    """Map a script's stage (+ its first argument) to a console stage."""
    s = ev.get("stage")
    argv = ev.get("argv") or []
    if s in ("size", "check"):
        return "risk"
    if s == "broker":
        return "sync" if argv[:1] == ["sync"] else "broker"
    return s


# ---------------------------------------------------------------- state

def _read(name, default=None):
    return store.read_json(store.path(name), default)


def stage_summary():
    evs, _ = activity.tail(0)
    runs = {}
    for ev in evs:
        rid = ev.get("run")
        if not rid:
            continue
        r = runs.setdefault(rid, {"run": rid, "stage": None, "start": ev["ts"], "end": None, "rc": None, "last": "", "level": "info", "args": ""})
        if ev["kind"] == "start":
            r["stage"] = ui_stage(ev)
            r["start"] = ev["ts"]
            r["args"] = ev.get("msg", "")
        elif ev["kind"] == "line":
            msg = ev.get("msg", "").strip()
            # "wrote <path>" says nothing on a stage card; keep the line before it.
            if not msg.startswith("wrote ") or not r["last"]:
                r["last"] = msg
            if ev.get("level") in ("fail", "warn", "ok") and r["level"] != "fail":
                r["level"] = ev["level"] if not (r["level"] == "warn" and ev["level"] == "ok") else r["level"]
        elif ev["kind"] == "end":
            r["end"] = ev["ts"]
            r["rc"] = ev.get("rc")
    out = {}
    now = time.time()
    for r in sorted(runs.values(), key=lambda x: x["start"]):
        if not r["stage"]:
            continue
        if r["end"] is None:
            status = "running" if now - r["start"] < 600 else "stalled"
        elif r["rc"] == 0:
            status = "warn" if r["level"] == "warn" else "ok"
        elif r["rc"] == 3:
            status = "waiting"
        else:
            status = "fail"
        out[r["stage"]] = {"status": status, "at": r["end"] or r["start"], "started": r["start"], "last": r["last"],
                           "args": r["args"], "run": r["run"],
                           "duration": round((r["end"] or now) - r["start"], 2)}
    return out


def build_state():
    cfg = store.load_config()
    now = store.now_utc(None, cfg.get("display_tz") or "UTC")
    scan = _read("scan.json", {}) or {}
    rows = []
    for ev in scan.get("results", []):
        w = ev.get("window") or {}
        row = {k: ev.get(k) for k in ("symbol", "range", "setup", "state", "side", "entry", "range_high", "range_low",
                                      "range_atr", "trend", "trigger_close_t", "source", "note", "last_close")}
        row.update(tz=w.get("tz"), until=w.get("until"))
        rows.append(row)
    evs, updated = E.load_all()
    upcoming = []
    for e in evs:
        t = store.parse_iso(e["t"])
        if now - _dt.timedelta(hours=1) <= t <= now + _dt.timedelta(hours=72) and e.get("impact") in ("High", "Medium"):
            upcoming.append({"title": e["title"], "country": e["country"], "impact": e["impact"], "t": e["t"],
                             "forecast": e.get("forecast"), "previous": e.get("previous")})
    replay = _read("replay.json")
    orders = (O.load() or {}).get("orders", [])
    verdicts = O.verdicts()
    olist = []
    sent_ids = {e.get("order_id") for e in L.load()["entries"] if e["kind"] == "sent"}
    approved = {(e.get("order_id"), e.get("fingerprint")) for e in L.load()["entries"] if e["kind"] == "approved"}
    for o in orders:
        v = verdicts.get(o.get("fingerprint"))
        status = "SENT" if o["id"] in sent_ids else ("APPROVED" if (o["id"], o.get("fingerprint")) in approved else
                 ("READY" if v and v["verdict"] == "PASS" else ("BLOCKED" if v else "UNCHECKED")))
        olist.append(dict(o, verdict=v, status=status))
    realized, open_risk, started = L.risk_today(cfg, now)
    lim = cfg["limits"]
    bal = float(cfg["account"]["balance"])
    daily = [x for x in (lim.get("daily_loss_limit_money"), bal * lim["daily_loss_limit_pct"] / 100 if lim.get("daily_loss_limit_pct") else None) if x]
    positions = [p for p in L.positions().values() if p.get("kind") == "open" and p["status"] not in ("proposed",)]
    positions.sort(key=lambda p: p.get("sent_ts") or "", reverse=True)
    entries = L.load()["entries"][-40:]
    return {
        "now": store.iso(now), "demo": DEMO["on"], "trader_dir": store.trader_dir(),
        "config": {"ccy": cfg["account"]["ccy"], "balance": bal, "paper": bool(cfg.get("paper", True)),
                   "broker": cfg.get("broker"), "display_tz": cfg.get("display_tz"),
                   "risk_pct": cfg["account"].get("risk_per_trade_pct"), "risk_money": cfg["account"].get("risk_per_trade_money"),
                   "max_trades": lim.get("max_trades_per_day"), "min_rr": lim.get("min_rr"),
                   "watchlist": cfg.get("watchlist", [])},
        "stages": STAGES, "stage_state": stage_summary(),
        "scan": {"at": scan.get("at"), "rows": rows, "errors": scan.get("errors", [])},
        "calendar": {"updated": updated, "upcoming": upcoming[:12]},
        "plan": _read("plan.json"),
        "replay": {"monte_carlo": replay.get("monte_carlo"), "history": {k: v for k, v in (replay.get("history") or {}).items() if k != "trades"},
                   "trades": (replay.get("history") or {}).get("trades", [])[-30:], "verdict": replay.get("verdict"),
                   "at": replay.get("at"), "symbol": (replay.get("plan") or {}).get("symbol")} if replay else None,
        "orders": olist,
        "today": {"realized": realized, "open_risk": open_risk, "trades": len(started), "daily_limit": min(daily) if daily else None},
        "positions": positions[:10],
        "ledger": entries,
    }


def state_fingerprint():
    out = []
    for n in WATCH:
        p = store.path(n)
        try:
            out.append((n, os.path.getmtime(p), os.path.getsize(p)))
        except OSError:
            out.append((n, 0, 0))
    return tuple(out)


# ---------------------------------------------------------------- runs (read-only stages only)

def script(rel):
    return os.path.join(PACK, rel)


ACTIONS = {
    "scan": lambda a: [script("fx-scanner/scan.py"), "--write"] + (["--symbols", a["symbols"]] if a.get("symbols") else []) + (["--setup", a["setup"]] if a.get("setup") in ("break", "sweep", "both") else []),
    "calendar": lambda a: [script("fx-calendar/events.py"), "fetch"],
    "plan_check": lambda a: [script("fx-entry-exit/plan.py"), "check", a["symbol"]],
    "replay": lambda a: [script("fx-timemachine/replay.py"), "run", "--write"],
    "size": lambda a: [script("fx-risk/size.py")],
    "check": lambda a: [script("fx-risk/check.py")],
    "sync": lambda a: [script("fx-broker/ticket.py"), "sync"],
    "show": lambda a: [script("fx-broker/ticket.py"), "show"],
}


def start_action(name, args):
    if name not in ACTIONS:
        raise ValueError("unknown action")
    for k in ("symbol", "symbols"):
        if k in args:
            vals = str(args[k]).split(",")
            if not all(SYMBOL_RE.match(v) for v in vals):
                raise ValueError("bad symbol")
    if name == "plan_check" and not args.get("symbol"):
        raise ValueError("symbol required")
    argv = [sys.executable] + ACTIONS[name](args)
    if DEMO["on"] and name in ("scan", "plan_check", "replay"):
        argv.append("--offline")
    env = dict(os.environ)
    env["FX_TRADER_DIR"] = store.trader_dir()
    subprocess.Popen(argv, env=env, cwd=os.path.dirname(store.trader_dir()), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return argv[1:]


# ---------------------------------------------------------------- demo

def demo_setup(base):
    sys.path.insert(0, os.path.join(PACK, "tests"))
    import _synth as SY
    from fxcore import bars as B, instruments as I

    os.environ["FX_TRADER_DIR"] = os.path.join(base, "trader")
    os.environ["FX_OFFLINE"] = "1"
    os.environ["FX_NOW"] = "2026-10-23 13:14"
    cfg = json.load(open(os.path.join(PACK, "fx-risk", "config.example.json")))
    cfg["broker"] = "signals"
    cfg["watchlist"] = ["XAUUSD", "EURUSD", "GBPUSD", "ES"]
    cfg["limits"]["acknowledge_specs"] = ["XAUUSD"]
    store.write_json(store.path("config.json"), cfg)
    day = _dt.date(2026, 10, 23)
    gold = SY.series("Europe/London", _dt.date(2026, 8, 3), 60, "00:00", "21:00", 2600.0, 0.8, seed=3)
    gold = SY.shape_day(gold, "Europe/London", day, "08:00", "08:30", 2650.0, 3.0,
                        [(2650, 2652, 2649, 2651.5), (2651.5, 2655, 2651, 2654.2), (2654.2, 2657, 2653.8, 2656.5)])
    B.save_cache("XAUUSD", 5, gold)
    B.save_cache("EURUSD", 5, SY.series("Europe/London", _dt.date(2026, 8, 3), 60, "00:00", "21:00", 1.08, 0.0003, seed=5))
    B.save_cache("GBPUSD", 5, SY.series("Europe/London", _dt.date(2026, 8, 3), 60, "00:00", "21:00", 1.29, 0.0004, seed=6))
    es = SY.series("America/New_York", _dt.date(2026, 7, 20), 70, "09:30", "16:00", 5800.0, 2.0, seed=11)
    spec = I.get("ES")
    B.save_cache("ES", 5, [(t, I.round_tick(o, spec), I.round_tick(h, spec), I.round_tick(l, spec), I.round_tick(c, spec), v) for t, o, h, l, c, v in es])
    E.save([
        {"title": "Core PCE Price Index m/m", "country": "USD", "t": "2026-10-23T12:30:00Z", "impact": "High", "forecast": "0.2%", "previous": "0.3%"},
        {"title": "UoM Consumer Sentiment", "country": "USD", "t": "2026-10-23T14:00:00Z", "impact": "Medium", "forecast": "57.1", "previous": "56.4"},
        {"title": "BOE Gov Bailey Speaks", "country": "GBP", "t": "2026-10-23T16:15:00Z", "impact": "High", "forecast": "", "previous": ""},
        {"title": "ECB President Lagarde Speaks", "country": "EUR", "t": "2026-10-24T09:00:00Z", "impact": "Medium", "forecast": "", "previous": ""},
    ])
    store.write_json(store.path("events.manual.json"), [{"title": "RBI policy (demo)", "country": "INR", "t": "2026-10-24T04:30:00Z", "impact": "High"}])
    t0 = store.parse_iso("2026-10-23T04:05:00Z")
    L.append({"kind": "sent", "order_id": "TDEMO0001", "symbol": "EURUSD", "side": "short", "qty": 0.3, "max_loss": 45,
              "order_kind": "open", "broker": "signals", "account_ccy": "USD"}, t0)
    L.append({"kind": "placed", "order_id": "TDEMO0001", "symbol": "EURUSD", "filled_qty": 0.3, "filled_price": 1.08412}, t0)
    L.append({"kind": "closed_leg", "order_id": "TDEMO0001", "symbol": "EURUSD", "qty": 0.1, "pnl": 15.0}, t0 + _dt.timedelta(minutes=34))
    L.append({"kind": "closed", "order_id": "TDEMO0001", "symbol": "EURUSD", "qty": 0.2, "pnl": 0.0}, t0 + _dt.timedelta(minutes=71))


def demo_loop():
    py = sys.executable
    steps = [
        ([script("fx-scanner/scan.py"), "--offline", "--setup", "both", "--write"], 2.0),
        ([script("fx-calendar/events.py"), "upcoming", "--hours", "36"], 1.5),
        ([script("fx-entry-exit/plan.py"), "check", "XAUUSD", "--offline"], 1.2),
        ([script("fx-entry-exit/plan.py"), "make", "XAUUSD", "--offline", "--write"], 1.5),
        ([script("fx-timemachine/replay.py"), "run", "--offline", "--runs", "10000", "--write"], 1.5),
        ([script("fx-risk/size.py"), "--write"], 1.2),
        ([script("fx-risk/check.py"), "--price", "2654.4"], 1.5),
        ([script("fx-broker/ticket.py"), "show"], 1.0),
        ([script("fx-broker/ticket.py"), "sync"], 14.0),
    ]
    while True:
        for argv, pause in steps:
            subprocess.run([py] + argv, env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(pause)


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "TradingConsole/1.0"

    def log_message(self, fmt, *args):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/state":
            return self._json(200, build_state())
        if path == "/api/events":
            return self._sse()
        return self._static(path)

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/run":
            return self._json(404, {"error": "not found"})
        # A custom header cannot be sent cross-site without a CORS preflight, which
        # this server never approves, so other websites cannot start runs here.
        if self.headers.get("X-FX-Console") != "1":
            return self._json(403, {"error": "missing X-FX-Console header"})
        origin = self.headers.get("Origin")
        if origin and not re.match(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$", origin):
            return self._json(403, {"error": "bad origin"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(n, 4096)) or b"{}")
            argv = start_action(body.get("action"), body.get("args") or {})
        except (ValueError, KeyError) as e:
            return self._json(400, {"error": str(e)})
        return self._json(202, {"started": [os.path.relpath(argv[0], PACK)] + argv[1:]})

    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        def send(event, data):
            self.wfile.write(("event: %s\ndata: %s\n\n" % (event, json.dumps(data, default=str))).encode("utf-8"))
            self.wfile.flush()

        try:
            evs, off = activity.tail(0, limit=300)
            for ev in evs:
                ev["ui_stage"] = ui_stage(ev)
            send("backlog", evs)
            send("state", build_state())
            fp = state_fingerprint()
            last_ping = time.time()
            last_state = time.time()
            while True:
                time.sleep(0.35)
                new, off = activity.tail(off)
                if new:
                    for ev in new:
                        ev["ui_stage"] = ui_stage(ev)
                    send("activity", new)
                nfp = state_fingerprint()
                if nfp != fp or (new and any(e["kind"] in ("start", "end") for e in new)) or time.time() - last_state > 20:
                    fp = nfp
                    last_state = time.time()
                    send("state", build_state())
                if time.time() - last_ping > 15:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    last_ping = time.time()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _static(self, path):
        if not os.path.isdir(DIST):
            body = ("<h1>Trading Console</h1><p>The UI is not built yet. In apps/fx-console run "
                    "<code>npm run build</code>, or <code>npm run dev</code> for the dev server.</p>").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
            return
        rel = os.path.normpath(path.lstrip("/")) if path not in ("", "/") else "index.html"
        full = os.path.join(DIST, rel)
        if not os.path.abspath(full).startswith(os.path.abspath(DIST)) or not os.path.isfile(full):
            full = os.path.join(DIST, "index.html")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trader-dir", help="the trader/ folder the skills write to (default ./trader)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--demo", action="store_true", help="run the pipeline on synthetic data in a temp folder")
    args = ap.parse_args(argv)
    if args.demo:
        DEMO["on"] = True
        base = tempfile.mkdtemp(prefix="fx-console-demo-")
        demo_setup(base)
        threading.Thread(target=demo_loop, daemon=True).start()
    elif args.trader_dir:
        os.environ["FX_TRADER_DIR"] = os.path.abspath(args.trader_dir)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    srv.daemon_threads = True
    print("Trading Console on http://127.0.0.1:%d  watching %s%s" % (args.port, store.trader_dir(), "  (DEMO)" if args.demo else ""), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if args.demo:
            shutil.rmtree(os.path.dirname(store.trader_dir()), ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
