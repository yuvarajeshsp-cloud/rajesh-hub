---
name: fx-entry-exit
description: >-
  Entry timer and exit planner for forex, gold CFDs and futures. Checks a
  range-breakout or liquidity-sweep setup bar by bar (waiting / triggered /
  expired), and writes the trade plan before entry: stop (range mid, far
  side of the range, sweep extreme plus buffer, ATR, ticks or a price),
  scale-out targets in R (default 1R/2R/3R in thirds), stop to breakeven
  after TP1, and the flat-by time for day-traded futures. Also plans a
  discretionary trade from your own entry and stop. Use when the user says
  "is it time to get in", "watch gold for the breakout", "where's my stop",
  "plan the trade", "set targets", "I want to buy here with a stop at X".
argument-hint: "SYMBOL [--setup break|sweep] [--stop METHOD] [--targets 1,2,3]"
---

# fx-entry-exit

```bash
python3 "${CLAUDE_SKILL_DIR}/plan.py" check XAUUSD --setup sweep --range london
python3 "${CLAUDE_SKILL_DIR}/plan.py" watch ES --range orb --every 30            # loops until triggered/expired
python3 "${CLAUDE_SKILL_DIR}/plan.py" make XAUUSD --setup sweep --stop extreme:30 --targets 1,2,3 --write
python3 "${CLAUDE_SKILL_DIR}/plan.py" make ES --stop range_mid --write
python3 "${CLAUDE_SKILL_DIR}/plan.py" manual XAUUSD --side long --entry 2650.20 --stop 2644.80 --write
```

`--write` saves `trader/plan.json`, which fx-timemachine and fx-risk read.

## Stops

| `--stop` | stop at |
| --- | --- |
| `range_mid` (default) | the middle of the range |
| `range_far` | the other side of the range |
| `extreme[:N]` | the trigger bar's low (long) / high (short), plus N ticks. Natural stop for a sweep |
| `atr:K` | K x the bar ATR(14) from entry |
| `ticks:N` | N ticks from entry |
| `price:P` | an exact price |

Ticks are the instrument's tick (XAUUSD 0.01, EURUSD 0.00001, ES 0.25).
Prices round away from entry for stops, to the nearest tick for targets.

## Targets

`--targets 1,2,3` are R multiples (R = entry-to-stop distance), `--split`
the share of the position at each (default thirds). TP1 hit moves the other
legs' stop to the entry price (`--no-be` to keep it). The executors carry
this out: MT5 as separate positions per target, NinjaTrader as one
stop+target OCO pair per leg. Defaults come from `plan` in `trader/config.json`.

## Steps

1. `check` (or `watch` while the user waits) and report the state in plain words.
2. When triggered, `make ... --write`. Show the plan: entry, stop (ticks and
   price distance), each target with its R and share, breakeven rule, flat-by.
3. If the user wants a different stop or targets, rebuild; never edit
   `plan.json` by hand.
4. Next: `/fx-timemachine` to replay it, then `/fx-risk`.

## Never

- Never move a stop further from entry after the plan is made; make a new plan.
- Never plan an entry on a bar that has not closed. `check` uses closed bars only.
- A planned entry is the trigger close; the real fill will differ. fx-risk
  checks the drift when given `--price`.
