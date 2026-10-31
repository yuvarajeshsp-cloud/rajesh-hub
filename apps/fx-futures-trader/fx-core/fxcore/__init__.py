"""Shared core for the fx-futures-trader skills (standard library only)."""

import os
import sys


def cli_setup():
    """Make console output safe on Windows code pages."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(errors="replace")
        except Exception:
            pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
