---
name: fx-broker
description: >-
  Order executor for forex, gold CFDs and futures, demo/sim by default and
  never without your yes. Shows each order as a plain ticket, records your
  yes word for word, then hands it to MetaTrader 5 (TicketExecutorEA, which
  re-checks the loss with the broker's contract and asks again on screen),
  NinjaTrader 8 (ATI order files: entry, then a stop + target OCO pair per
  leg, breakeven after TP1, or an ATM template), or to you (signals only:
  MCX, NSE, any broker). Syncs fills and closes back for the daily loss
  limit, and builds the close ticket to flatten. Use when the user says
  "place it", "send it", "buy", "sell", "execute", "flatten", "close my
  trade", "set up MT5 / NinjaTrader", or after /fx-risk passes.
argument-hint: "[show | approve | send | sync | flatten] [--index N]"
---

# fx-broker

The only skill that can lead to an order, so it is the strictest. An order
goes out only when **all** of these hold, every time, for every order:

1. **fx-risk passed this exact order** (fingerprint) in the last 15 minutes.
2. **The user typed an explicit yes for this one ticket** in the chat, recorded
   by `approve` in the last 10 minutes (`approval_valid_min`).
3. **The platform's own check**: Claude Code asks before `ticket.py send`
   (see setup), and on MT5 the EA shows a Yes/No box; on NinjaTrader the
   account must be a Sim account while `paper` is true.

```bash
python3 "${CLAUDE_SKILL_DIR}/ticket.py" show
python3 "${CLAUDE_SKILL_DIR}/ticket.py" approve --index 1 --reply "<the user's reply, word for word>"
python3 "${CLAUDE_SKILL_DIR}/ticket.py" send --index 1
python3 "${CLAUDE_SKILL_DIR}/ticket.py" sync              # fills, TP/stop hits, P&L
python3 "${CLAUDE_SKILL_DIR}/ticket.py" flatten --order <ID>   # close ticket, then check.py, yes, send
python3 "${CLAUDE_SKILL_DIR}/ticket.py" fill --order <ID> --qty 1 --price 74250    # signals mode
python3 "${CLAUDE_SKILL_DIR}/ticket.py" close --order <ID> --price 74390 --qty 1   # signals mode
python3 "${CLAUDE_SKILL_DIR}/ticket.py" log
```

## Which instruments go where

| `broker` | instruments | how |
| --- | --- | --- |
| `mt5` | forex, XAUUSD, XAGUSD (anything with an MT5 symbol) | ticket file -> TicketExecutorEA |
| `ninjatrader` | CME futures (ES, MES, NQ, MNQ, YM, GC, MGC, SI, CL, MCL, 6E) | ATI `oif*.txt` files |
| `signals` | everything, and the only route for MCX and NSE | you place it; record fills |

## Setup: Claude Code permission (every route)

Keep `send` on ask so Claude's own card is one more check. In
`.claude/settings.json` of the project:

```json
{"permissions": {"ask": ["Bash(python3 *ticket.py send*)"]}}
```

Never put it under `allow`.

## Setup: MetaTrader 5

1. From rajesh-hub `packages/trading`: copy `mql5/Include/RajeshHub/` to
   `<MT5 data folder>/MQL5/Include/RajeshHub/` and `mt5/TicketExecutorEA.mq5`
   to `MQL5/Experts/`. Compile in MetaEditor.
2. Log in to a **demo** account. Attach the EA to any one chart. Allow Algo
   Trading. Inputs: start with `EnableTrading=false` (dry run: it checks and
   logs every ticket, trades nothing), `RequireDemo=true`,
   `ConfirmEachTicket=true`.
3. `brokers.mt5.folder` in `trader/config.json` must equal the EA's
   `TicketFolder` (default `RajeshHub\tickets`). Tickets go to
   `%APPDATA%\MetaQuotes\Terminal\Common\Files\RajeshHub\tickets\pending`
   (set `brokers.mt5.common_files` if Claude runs as another user or the
   files must be copied to a VPS).
4. What the EA does with a ticket: drops it after 120 s; refuses a real-money
   account while the ticket or the EA requires demo; checks the volumes, stop
   side and TPs; **recomputes the loss at the stop with OrderCalcProfit and
   refuses if it is more than 10 % over the approved max loss** (catches a
   wrong contract size); shows Yes/No; opens one position per target with
   the same stop; moves the others to breakeven when TP1 fills; closes at
   the flat-by time; writes `results\<id>.json` for `sync`.
5. Turn `EnableTrading` on only after watching dry-run tickets in the Experts log.

## Setup: NinjaTrader 8

1. Tools > Options > Automated trading interface: enable **AT Interface**.
   Connect the Sim101 (or a funded/sim) account.
2. `brokers.ninjatrader.account` (default `Sim101`) and `contract_months`
   for each future (`"ES": "12-26"`). Roll them yourself before expiry.
3. `mode: "protect"` (default): `send` writes a market entry
   (`PLACE;Sim101;ES 12-26;BUY;2;MARKET;0;0;DAY;;<id>E;;`), waits for the
   fill in `outgoing\<id>E.txt`, then writes one STOPMARKET + LIMIT pair per
   leg sharing an OCO id. **If the fill is not seen within `--wait` seconds,
   run `sync` at once: the position has no stop until it does.** `sync` also
   moves the other legs' stops to the fill price when TP1 fills.
4. `mode: "atm"`: one entry with your ATM strategy template, which carries
   the stop and targets inside NinjaTrader (no unprotected gap). Describe the
   template in `atm_templates` (`{"stop_ticks": 16, "target_ticks": [16, 32, 48], "qty": [1, 1, 1]}`)
   and name it in `atm_template`; `send` refuses when the plan does not match it.
5. Flatten writes `CLOSEPOSITION` (or `CLOSESTRATEGY` for ATM) plus cancels for our stop/target orders.

## Steps: the entry

1. `show`. Only READY tickets go to the user. NOT READY or BLOCKED goes back to `/fx-risk`.
2. Show ONE ticket in plain words and ask: "Place ticket N? Reply yes or no."
   One ticket per question. Never offer "yes to all".
3. `approve --index N --reply "<their reply word for word>"`. "Not recorded"
   means it was not a clean yes for this ticket (it said no/wait/all, or named
   another symbol, size or price). Ask again. Never turn a reply into a yes yourself.
4. After "Recorded your yes": `send --index N`.
5. `sync` (or `sync --watch 30` while they wait) and report fills, TP hits,
   breakeven moves and P&L. Signals mode: ask for the fill and run `fill`, later `close`.

## Steps: getting out

`flatten --order ID` -> `/fx-risk` `check.py` (a close only needs an open
trade) -> `show` -> the user's yes -> `send`. Futures day trades are flat by
the plan's flat-by time (the MT5 EA does this itself; on NinjaTrader set an
alert or flatten by then).

## Never

- Never send without all three gates, never two tickets on one yes.
- Never send from a scheduled or background task: nobody is there to say yes.
- Never switch `paper` off, `RequireDemo` off, `EnableTrading` on, or a live
  NinjaTrader account in. The user does that, in their own config.
- Never ask for, read, store or repeat passwords, API keys or account numbers.
- Never promise a fill price. Market orders and stops fill at what the market gives.
