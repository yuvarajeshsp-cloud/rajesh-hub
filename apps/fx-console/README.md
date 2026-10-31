# Trading Console

A live window into the fx-futures-trader skills: what the backend is doing,
stage by stage, as it happens.

- **Pipeline rail**: Scanner → Calendar → Entry/Exit → Time machine → Risk gate → Broker → Sync.
  Each card lights up while its script runs (pulse, sweep, flowing connector),
  then shows done / waiting / done-with-notes / blocked, its last meaningful
  line, when it ran and how long it took.
- **Backend activity**: every line each script prints, streamed live, grouped by
  run and coloured by result (PASS green, notes gold, BLOCK red), filterable by stage.
- **Trade plan** as a price ladder (range, entry, stop, TP1-TP3 with R and share).
- **Time machine**: stop-first and TP odds, average R, verdict, and one square per real past trade.
- **Risk gate**: PASS/BLOCK with every reason and note, ticket status.
- **Today**: realized P&L, open risk, trades used, daily-loss-limit bar, recent trades.
- **Scanner** results and **News ahead** with live countdowns.
- Clocks for IST, London and New York.

## Run it

```bash
cd apps/fx-console
npm run build                       # once, and after UI changes
python3 server.py                   # watches ./trader; open http://127.0.0.1:8765
python3 server.py --trader-dir "D:\trading\trader"
python3 server.py --demo            # self-running pipeline on synthetic data
```

Run the server from the folder where you run the skills (or pass
`--trader-dir`), because that is where `trader/` lives. For UI work:
`python3 server.py` in one terminal and `npm run dev` in another (Vite
proxies `/api` to the server).

## How it knows what is happening

Every skill script runs through `fxcore/activity.py`, which appends one JSON
event per start, printed line and end to `trader/state/activity.jsonl`. The
server tails that file and the `trader/*.json` state files and pushes changes
to the browser over Server-Sent Events (`/api/events`). Nothing is polled
from the broker; the console shows what the skills did.

## Safety

- The server binds to 127.0.0.1 only.
- The buttons start **read-only** stages: scan, calendar fetch, replay, risk
  check, sync. Approving, sending and flattening orders are not available
  here at all; they stay in the chat, behind your yes and fx-risk's PASS.
- Run requests need the `X-FX-Console` header (blocks other websites) and only
  accept symbols matching `[A-Za-z0-9_]`.

Standard-library Python for the server; React, Tailwind and `@rajesh-hub/ui`
for the page, colours from `@rajesh-hub/tokens`.
