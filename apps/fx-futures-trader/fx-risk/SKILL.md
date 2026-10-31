---
name: fx-risk
description: >-
  Position sizing and risk gate for forex lots, gold CFDs and futures
  contracts (CME, MCX, NSE). Sizes from your max loss per trade using each
  instrument's tick size and tick value with currency conversion (USD, INR,
  JPY...), splits across the plan's targets, estimates margin, then checks
  the exact order against your limits: per-trade loss, daily loss, trades per
  day, reward/risk, entry window, signal age, flat-by, news blackout, weekend
  gap, margin, spec verification, paper mode, stacking, price drift and
  spread. PASS or BLOCK with the reason. Use when the user says "how many
  lots", "size it", "how many contracts", "check the risk", "is this within
  my limits", or before /fx-broker.
argument-hint: "[--balance N] [--risk-pct P] [--price P]"
---

# fx-risk

```bash
python3 "${CLAUDE_SKILL_DIR}/size.py"                       # preview: trader/plan.json -> an order
python3 "${CLAUDE_SKILL_DIR}/size.py" --write               # -> trader/orders.json
python3 "${CLAUDE_SKILL_DIR}/size.py" --balance 5000 --risk-pct 0.5 --broker mt5 --write
python3 "${CLAUDE_SKILL_DIR}/check.py" --price 2654.6 --spread 25   # PASS / BLOCK, recorded in trader/state/risk.json
```

## Set up once: trader/config.json

Copy `config.example.json` (this folder) to `trader/config.json` and set:

- `account.ccy` and `account.balance` (the account the orders go to), and
  `risk_per_trade_pct` or `risk_per_trade_money`.
- `rates` for every currency pair the sizing needs, e.g. an INR account
  trading XAUUSD needs `"USDINR"`; any account trading USDJPY needs `"USDJPY"`.
  Sizing refuses to guess a missing rate.
- `broker`: `signals`, `mt5` or `ninjatrader`, and `paper: true` until you
  have watched it work.
- `limits`: the gate below.

## Sizing

`loss per unit = ticks from entry to stop x tick value` (one lot or one
contract), converted to the account currency. `size = floor(risk / loss per
unit)` on the instrument's step (0.01 lot, 1 contract), capped at `max_qty`.
If even the minimum size loses more than your risk it says so and suggests
the micro / mini contract (MES, MNQ, MGC, MCL, GOLDM, CRUDEOILM...).

The size is split across targets on the step. 1 contract cannot be split
three ways: the extra targets are dropped and the order says so.

## Specs to check before going live

`scan.py list` shows `VERIFY` for specs that depend on your broker or change:
XAUUSD/XAGUSD CFDs (contract size), all MCX contracts, all NSE contracts (lot
sizes as of January 2026: NIFTY 65, BANKNIFTY 30, FINNIFTY 60, MIDCPNIFTY
120; tick size). Fix them in `trader/instruments.json`, then set
`"verified": true` there or add the symbol to `limits.acknowledge_specs`.
Until then the gate BLOCKs them. (The MT5 executor also recomputes the loss
with the broker's own contract and refuses anything over the approved loss.)

## The gate (check.py)

| rule | config |
| --- | --- |
| max loss per trade | `max_risk_pct`, `max_risk_money` (the smaller wins) |
| daily loss: today's losses + open risk at stops + this trade | `daily_loss_limit_pct`, `daily_loss_limit_money` |
| trades started today | `max_trades_per_day` |
| weighted reward/risk | `min_rr` |
| signal age, entry window, 10 min before flat-by | `signal_max_age_min`, plan's `valid_until` |
| news blackout | fx-calendar, `news_blackout_*`, `news_impacts` |
| no new forex/CFD trades from 1 h before Friday's close to Sunday's open | instrument `weekend_cutoff` |
| margin under a share of balance | `max_margin_pct` (futures: set `margin.per_contract`) |
| size caps | instrument `max_qty`, `limits.max_qty.{SYMBOL}` |
| paper mode: order marked paper, NinjaTrader account named Sim* | `paper` |
| one open trade per symbol | `allow_stacking` |
| price drift from plan, price through stop (with `--price`) | `max_entry_drift_r` |
| spread (with `--spread` ticks) | `max_spread_ticks` |
| the order not edited after sizing | fingerprint |

The "day" is your `display_tz` day (IST by default).

## Steps

1. `size.py` and show the order in words: lots/contracts per leg, max loss in
   the account currency, reward/risk, margin, any dropped target or VERIFY note.
2. If the user agrees, `size.py --write`, then `check.py` (with `--price`
   and `--spread` when you have a live quote).
3. Report PASS or each BLOCK reason. Never work around a BLOCK by editing
   files or changing limits on your own: changing a limit is the user's call,
   in their config.
4. On PASS: `/fx-broker`.

## Never

- Never raise a limit, acknowledge a spec, or switch `paper` off yourself.
- A PASS is a rules check, not advice to trade.
