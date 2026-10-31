# fx-futures-trader

Six Claude skills for day trading **forex, gold/silver CFDs and futures**:
CME (ES, NQ, YM, GC, SI, CL, 6E and the micros), MCX (gold, silver, crude,
natural gas, minis) and NSE index futures (Nifty, Bank Nifty, Fin Nifty,
Midcap Select).

Plain standard-library Python 3.8+, nothing to pip install. Optional:
`pip install MetaTrader5` on Windows to read bars straight from your MT5
terminal. Orders go to **MetaTrader 5**, **NinjaTrader 8** or to **you**
(signals only), on demo/sim accounts by default, and never without your yes.

Modelled on the structure of
[Jakeschincariol/day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill)
(US stocks), rebuilt for lots, ticks, contract specs, sessions and these
brokers. The MT5 side extends rajesh-hub `packages/trading`.

## The six

| command | job |
| --- | --- |
| `/fx-scanner` | Range breakouts (Asian range, London open, US open, MCX/NSE opening range) and liquidity sweeps across the watchlist, with range vs daily ATR and trend. Imports MT5 / NinjaTrader CSV exports. |
| `/fx-calendar` | ForexFactory weekly calendar + your own India events (RBI, Budget, expiry). CLEAR / BLACKOUT for any instrument at any time. |
| `/fx-entry-exit` | Watches a setup bar by bar, then writes the plan: stop (range mid / far / sweep extreme / ATR / ticks / price), 1R-2R-3R in thirds, breakeven after TP1, flat-by time. Also plans your own discretionary trade. |
| `/fx-timemachine` | Replays the rest of the session 10,000 times from the instrument's own bars at the same time of day over 60 sessions, plus the same rule on every real past session. |
| `/fx-risk` | Lots or contracts from your max loss, with tick values and currency conversion (USD / INR / JPY...), split per target, margin estimate; then PASS / BLOCK against your limits. |
| `/fx-broker` | Plain ticket, your yes word for word, then MT5 (TicketExecutorEA), NinjaTrader (ATI files) or signals. Syncs fills and P&L back for the daily limit. |

## One trade

```
scanner -> calendar -> entry-exit -> timemachine -> risk (size, check) -> broker (show, yes, send, sync)
```

```bash
python3 fx-scanner/scan.py --symbols XAUUSD,EURUSD,ES --setup both
python3 fx-calendar/events.py fetch && python3 fx-calendar/events.py blackout XAUUSD
python3 fx-entry-exit/plan.py make XAUUSD --setup sweep --stop extreme:30 --write
python3 fx-timemachine/replay.py run --write
python3 fx-risk/size.py --write && python3 fx-risk/check.py --price 2654.6
python3 fx-broker/ticket.py show
python3 fx-broker/ticket.py approve --index 1 --reply "yes"
python3 fx-broker/ticket.py send --index 1
python3 fx-broker/ticket.py sync --watch 30
```

Everything is written to `trader/` in the folder you run from (or
`FX_TRADER_DIR`): `config.json`, `instruments.json` (your spec overrides),
`bars/`, `events.json`, `plan.json`, `replay.json`, `orders.json`, `state/`.

## Live console

`apps/fx-console` shows every stage as it runs, with the streamed output of each
script, the plan, the odds, the risk verdict and today's limits:
`cd apps/fx-console && npm run build && python3 server.py` (or `--demo`).

## Install

In Claude Code, from the hub:

```
/plugin marketplace add yuvarajeshsp-cloud/rajesh-hub
/plugin install fx-futures-trader@rajesh-hub
```

Or copy the folders (keep `fx-core` next to the skills, they share it):

```bash
cp -r apps/fx-futures-trader/fx-* ~/.claude/skills/
```

Then `cp fx-risk/config.example.json trader/config.json` and edit it
(account currency and balance, risk, rates, broker, limits). See each
`SKILL.md` for details; `fx-broker/SKILL.md` has the MT5 and NinjaTrader setup.

## Where each market can go

| | data | execution |
| --- | --- | --- |
| Forex, XAUUSD, XAGUSD | MT5 package, CSV, Yahoo (gold/silver via COMEX futures as a proxy) | MT5 |
| CME futures | Yahoo, NinjaTrader CSV export | NinjaTrader 8 |
| MCX | CSV from your broker | signals only |
| NSE index futures | Yahoo cash index (proxy), CSV | signals only |

## Safety

- **Demo first.** `paper: true` by default. The MT5 EA refuses real-money
  accounts while `RequireDemo` is on and starts in dry-run
  (`EnableTrading=false`). NinjaTrader orders must go to a `Sim*` account while
  `paper` is true.
- **Three gates per order**: fx-risk PASS on that exact order (fingerprint),
  your explicit yes in the chat for that one ticket (recorded, valid 10
  minutes), and the platform's own check (Claude Code asks before `send`; the
  EA shows Yes/No).
- **The MT5 EA re-checks the money.** It recomputes the loss at the stop with
  your broker's own contract (OrderCalcProfit) and refuses anything more than
  10 % over what you approved, so a wrong lot size or tick value on the Python
  side cannot make a bigger trade than the ticket said.
- **Specs that vary are marked VERIFY** (gold/silver CFDs, all MCX and NSE
  contracts) and blocked until you confirm them. NSE lot sizes are as of the
  January 2026 expiry (Nifty 65, Bank Nifty 30); NSE revises them.
- **NinjaTrader protect mode** places the stop/targets after the entry fill
  is seen. Until `sync` runs, the position has no stop. Use an ATM template
  (`mode: "atm"`) to have NinjaTrader hold the brackets itself.
- **Not financial advice.** This is arithmetic on bars. Most day traders lose
  money, leveraged products more so. The time machine is a resampling of 60
  sessions, not a forecast; stops can fill worse than their price.
- **Data is free and unofficial** (Yahoo, ForexFactory). Check anything that
  matters against your broker.

## Tests

```bash
cd apps/fx-futures-trader && python3 -m unittest discover -s tests -v
```

36 offline tests on synthetic bars: time zones and DST against the system
database, CSV readers (MT5 server time, NinjaTrader bar-end stamps), both
setups, stops and the trade walk, the replay's determinism, sizing in USD and
INR accounts, every risk rule, the yes rules, the MT5 ticket file and result
sync, the full NinjaTrader flow (entry, protection, breakeven, flatten) and
signals mode. The MQL5 EA is not covered by these tests: compile it in
MetaEditor and run it on a demo account in dry-run first.
