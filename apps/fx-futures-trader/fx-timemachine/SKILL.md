---
name: fx-timemachine
description: >-
  Time machine for a planned forex/gold/futures trade: replays the rest of
  the session thousands of times (default 10,000, seeded) by drawing each
  bar from the instrument's own bars at that time of day over the last 60
  sessions, walks the plan's stop, scale-out targets and breakeven rule
  through every path, and re-runs the same setup rule on every real past
  session it fired. Reports stop-first odds, TP1/TP2/TP3 odds, average R and
  a plain verdict. Use when the user asks "what are the odds", "replay it",
  "backtest this setup", "is this worth taking", or before /fx-risk.
argument-hint: "[--runs N] [--seed S] [--sessions N]"
---

# fx-timemachine

```bash
python3 "${CLAUDE_SKILL_DIR}/replay.py" run                       # trader/plan.json, cached bars
python3 "${CLAUDE_SKILL_DIR}/replay.py" run --runs 20000 --seed 19 --sessions 60 --write
python3 "${CLAUDE_SKILL_DIR}/replay.py" run --source auto         # refresh bars first
```

## What it does

1. **Monte Carlo.** For every bar slot from the signal to the flat-by time
   (or the range's hold horizon), it picks one past session's bar at that same
   time of day and applies its open/high/low/close relative to the previous
   close. 10,000 paths, the same seed gives the same numbers.
2. **The walk.** Each path runs the real plan: a bar that touches both the
   stop and a target counts as the stop (conservative); a gap through the stop
   fills at the open; after TP1 the stop moves to entry if the plan says so;
   whatever is still open at the end closes at the last price.
3. **History.** The same rule (setup, range, stop method, targets) on each of
   the last N real sessions: how often it fired, which side, and how each one ended.
4. **Verdict.** "leans positive", "close to a coin flip" or "leans negative"
   from the average R of both, and "too few to trust" under 20 past trades.

## Steps

1. Needs `trader/plan.json` (fx-entry-exit `make --write`) and bars in the
   cache (any fx-scanner run). A `manual` plan gets the Monte Carlo only.
2. Run it and give the numbers in plain words: "in 10,000 replays the stop
   came first 46 % of the time; TP1 was reached 54 %, TP3 15 %; average
   +0.11R. On the last 59 sessions the rule fired 58 times and averaged +0.05R:
   close to a coin flip."
3. Say what it cannot see: news, spread, slippage, and anything the last 60
   sessions never did.

## Never

- Never call the output a forecast or a probability of profit. It is a
  resampling of recent bars.
- Never tune the stop/targets on the history until the numbers look good and
  then present them as an edge: that is curve fitting. Say so if asked to.
