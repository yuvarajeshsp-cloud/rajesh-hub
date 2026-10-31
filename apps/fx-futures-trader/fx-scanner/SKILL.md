---
name: fx-scanner
description: >-
  Chart scanner for forex, gold/silver CFDs, CME futures (ES, NQ, GC, CL and
  micros) and Indian MCX/NSE futures. Finds range breakouts (Asian range,
  London open, US open, MCX/NSE opening range) and liquidity sweeps (a bar
  that runs the range high/low and closes back inside), with range size vs
  daily ATR and trend. Also lists instrument specs and imports MT5 or
  NinjaTrader CSV exports. Use when the user says "scan", "any setups",
  "what's breaking out", "check gold / EURUSD / ES", "Asian range",
  "London breakout", "liquidity sweep", "import my MT5 data", or starts the
  trading day.
argument-hint: "[symbols] [--setup break|sweep|both] [--range NAME]"
---

# fx-scanner

First step of the pack. Everything lands in `trader/` in the current folder
(or `FX_TRADER_DIR`). `${CLAUDE_SKILL_DIR}` is this skill's folder.

```bash
python3 "${CLAUDE_SKILL_DIR}/scan.py"                                   # the watchlist in trader/config.json
python3 "${CLAUDE_SKILL_DIR}/scan.py" --symbols XAUUSD,EURUSD --setup both --range london
python3 "${CLAUDE_SKILL_DIR}/scan.py" --symbols ES,NQ,GC --range orb --write
python3 "${CLAUDE_SKILL_DIR}/scan.py" list                               # specs, brokers, VERIFY flags
python3 "${CLAUDE_SKILL_DIR}/scan.py" import XAUUSD ~/Downloads/XAUUSD_M5.csv --csv-tz NY+7
```

`--now "2026-10-23 14:45"` pins the clock (read in `display_tz`, IST by default).

## Data, in order of preference

1. **A CSV export** loaded once with `import` (every skill then reads it from the cache). MT5: right-click
   chart > Bars > Export (or Ctrl+U). NinjaTrader: Tools > Historical Data >
   Export. MT5 servers usually run on "NY+7" time (GMT+2 winter / GMT+3
   summer); pass `--csv-tz NY+7` or `UTC+2`. NinjaTrader exports bar CLOSE
   times; the reader shifts them to bar start.
2. **The MetaTrader5 Python package** (Windows, MT5 open): `pip install MetaTrader5`.
   Used automatically for symbols with an MT5 name. Your broker's own prices.
3. **Yahoo Finance** (free, unofficial, can lag). Forex pairs, CME futures,
   and Nifty/Bank Nifty as the cash index. Gold/silver CFDs fall back to
   COMEX futures as a **proxy**: levels differ from your broker by the basis.
4. **The cache** `trader/bars/` (whatever was loaded before). `--offline` uses only this.

MCX has no free feed here: import a CSV from your broker's terminal.

## Ranges (per instrument, edit in trader/instruments.json)

| instrument | ranges (local time) |
| --- | --- |
| forex majors, XAUUSD | `asia` 00:00-07:00 London; `london` 08:00-08:30 London; `ny` 08:30-09:00 New York (gold: 08:20-08:50) |
| JPY pairs | adds `tokyo` 09:00-09:30 Tokyo |
| ES, NQ, YM, micros | `orb` 09:30-09:45 New York, flat by 15:55 |
| GC, MGC, SI | `orb` 08:20-08:35 New York, flat by 13:25 |
| CL, MCL | `orb` 09:00-09:15 New York, flat by 14:25 |
| MCX gold/silver/crude | `orb` 09:00-09:15 IST, `us_open` 09:30-09:45 New York, flat by 23:15 IST |
| NIFTY, BANKNIFTY | `orb` 09:15-09:30 IST, flat by 15:15 IST |

Each range is valid until its `until` time; after that the state is `expired`.

## States

`waiting_for_range` · `forming` (range still building) · `waiting` (range
done, no trigger) · `triggered` (side, bar, close) · `expired` · `filtered`
(`--min-range-atr` / `--max-range-atr`) · `no_data`.

## Steps

1. Run the scan for what the user asked (default: the watchlist, `break`).
2. Show the table. For each `triggered` row say what fired, at what time in
   the market's zone and IST, and how big the range is vs daily ATR (a
   range under ~0.15x ATR is noise; over ~0.6x often means the move already happened).
3. Point out any proxy data source.
4. Offer the next step: `/fx-calendar` for news, then `/fx-entry-exit` on the one they pick.

## Never

- Never call a scan result a recommendation. It is a rule firing on bars.
- Never present proxy (Yahoo futures) prices as broker prices.
