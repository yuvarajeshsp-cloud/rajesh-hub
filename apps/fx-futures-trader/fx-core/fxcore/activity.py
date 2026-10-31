"""Activity stream: every skill run writes what it is doing, line by line, to
trader/state/activity.jsonl so the Trading Console can show it live.

Each line is one JSON event:
  {"ts", "run", "stage", "kind": "start"|"line"|"end", "msg", "rc", "argv", "level"}

Scripts opt in with:   sys.exit(activity.run("scan", main))
Tests call main() directly, so they never write here.
"""

import json
import os
import sys
import threading
import time
import uuid

from . import store

_LOCK = threading.Lock()
MAX_BYTES = 4 * 1024 * 1024


def log_path():
    return store.path("state", "activity.jsonl")


def emit(stage, kind, msg="", run_id=None, **extra):
    if os.environ.get("FX_ACTIVITY") == "0":
        return
    ev = {"ts": round(time.time(), 3), "run": run_id, "stage": stage, "kind": kind, "msg": msg}
    ev.update(extra)
    p = log_path()
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with _LOCK:
            if os.path.exists(p) and os.path.getsize(p) > MAX_BYTES:
                os.replace(p, p + ".1")
            with open(p, "a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except OSError:
        pass   # the console is optional; never break a trading script over it


def _level(line):
    u = line.upper()
    if "BLOCK" in u or "ERROR" in u or "NOT SENT" in u or "NO ORDER" in u or "REJECT" in u:
        return "fail"
    if "WARNING" in u or "NOTE" in u or "NOT RECORDED" in u or "VERIFY" in u:
        return "warn"
    if "PASS" in u or "TRIGGERED" in u or "RECORDED YOUR YES" in u or "SENT" in u or "WROTE" in u:
        return "ok"
    return "info"


class _Tee:
    def __init__(self, inner, stage, run_id):
        self.inner, self.stage, self.run_id, self.buf = inner, stage, run_id, ""

    def write(self, s):
        self.inner.write(s)
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if line.strip():
                emit(self.stage, "line", line.rstrip(), self.run_id, level=_level(line))
        return len(s)

    def flush(self):
        self.inner.flush()

    def __getattr__(self, name):
        return getattr(self.inner, name)


def run(stage, main, argv=None):
    """Run a script's main() and stream its output as activity events."""
    run_id = uuid.uuid4().hex[:10]
    args = list(sys.argv[1:] if argv is None else argv)
    emit(stage, "start", " ".join(args), run_id, argv=args)
    real = sys.stdout
    sys.stdout = _Tee(real, stage, run_id)
    rc = 1
    try:
        rc = main(argv)
        rc = 0 if rc is None else rc
        return rc
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        raise
    except Exception as e:
        emit(stage, "line", "error: %s" % e, run_id, level="fail")
        raise
    finally:
        out = sys.stdout
        sys.stdout = real
        if isinstance(out, _Tee) and out.buf.strip():
            emit(stage, "line", out.buf.rstrip(), run_id, level=_level(out.buf))
        emit(stage, "end", "", run_id, rc=rc)


def tail(since_bytes=0, limit=None):
    """(events, new_offset) read from byte offset `since_bytes`."""
    p = log_path()
    if not os.path.exists(p):
        return [], 0
    size = os.path.getsize(p)
    if since_bytes > size:          # rotated
        since_bytes = 0
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        f.seek(since_bytes)
        data = f.read()
        off = f.tell()
    evs = []
    for ln in data.splitlines():
        try:
            evs.append(json.loads(ln))
        except ValueError:
            pass
    if limit:
        evs = evs[-limit:]
    return evs, off
