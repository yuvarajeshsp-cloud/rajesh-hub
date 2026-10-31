---
name: fx-calendar
description: >-
  Economic calendar and news blackout for forex, gold and futures: this
  week's ForexFactory calendar (NFP, CPI, FOMC, ECB, BoE...), plus your own
  events for India (RBI policy, Union Budget, MCX/NSE expiry), and a CLEAR /
  BLACKOUT answer for any instrument at any time. fx-risk blocks entries
  inside the blackout window. Use when the user asks "any news", "what's on
  the calendar", "is NFP today", "can I trade gold now", "add RBI policy",
  or before planning a trade.
argument-hint: "[fetch | upcoming | blackout SYMBOL | add]"
---

# fx-calendar

```bash
python3 "${CLAUDE_SKILL_DIR}/events.py" fetch                              # ForexFactory this week -> trader/events.json
python3 "${CLAUDE_SKILL_DIR}/events.py" upcoming --hours 24 --symbols XAUUSD,ES,MCX_GOLD
python3 "${CLAUDE_SKILL_DIR}/events.py" blackout XAUUSD                    # exit code 0 CLEAR, 2 BLACKOUT
python3 "${CLAUDE_SKILL_DIR}/events.py" add --title "RBI policy" --country INR --at "2026-12-05 10:00" --tz Asia/Kolkata
python3 "${CLAUDE_SKILL_DIR}/events.py" add --title "NIFTY monthly expiry" --country NIFTY --at "2026-11-24 15:30"
```

## How it decides

- Each instrument lists the currencies that move it (`currencies` in its
  spec): XAUUSD -> USD; EURUSD -> EUR, USD; ES -> USD; MCX gold -> USD, INR;
  NIFTY -> INR. An event matches when its country is one of those, the
  instrument's own symbol, or `ALL`.
- Blackout = from `news_blackout_before_min` (15) before to
  `news_blackout_after_min` (15) after any event whose impact is in
  `news_impacts` (default `["High"]`), all in `trader/config.json` `limits`.
- ForexFactory covers USD, EUR, GBP, JPY, AUD, NZD, CAD, CHF, CNY. It does
  not cover INR: add RBI, Budget, CPI India and expiry days yourself with `add`
  (stored in `trader/events.manual.json`).
- The feed holds the current week only. Fetch it at the start of each week
  (or each day). fx-risk warns when the stored calendar is missing or stale.

## Steps

1. `fetch` if the calendar is older than a day (the output says so).
2. `upcoming` for the instruments in play; list high-impact items in IST and
   the market's zone, with forecast and previous.
3. For a specific trade, `blackout SYMBOL` (and with `--at` for the planned
   hold, e.g. before the flat-by time).
4. If a high-impact event falls while a day trade would be open, say so
   plainly; fx-risk will also flag it.

## Never

- Never guess a release time from memory; use the stored calendar or ask.
- The feed is free and unofficial. For a decision that matters, confirm the
  time on the central bank / statistics office site.
