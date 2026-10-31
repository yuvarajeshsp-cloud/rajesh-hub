import { CalendarClock, Check, Crosshair, Gauge, Hand, Radar, Rewind, ShieldCheck, TrendingDown, TrendingUp, TriangleAlert, Wallet, X } from "lucide-react"
import { Badge, Card, CardContent, CardHeader, CardTitle, cn } from "@rajesh-hub/ui"
import type { ReactNode } from "react"
import { clock, decimalsFor, money, pct, price, type ConsoleState, type Plan } from "../lib/api"

function Panel({ icon, title, right, children, className }: { icon: ReactNode; title: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("gap-0 overflow-hidden border-border/70 bg-card/80 py-0 backdrop-blur", className)}>
      <CardHeader className="flex flex-row items-center justify-between gap-2 border-b border-border/60 px-4 py-3">
        <CardTitle className="flex items-center gap-2 text-sm">{icon}{title}</CardTitle>
        {right}
      </CardHeader>
      <CardContent className="p-4">{children}</CardContent>
    </Card>
  )
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-muted-foreground">{children}</p>
}

// ---------------------------------------------------------------- the plan as a price ladder

export function PlanCard({ plan, tz }: { plan: Plan | null; tz: string }) {
  if (!plan)
    return (
      <Panel icon={<Crosshair className="size-4 text-brand-blue" />} title="Trade plan">
        <Empty>No plan yet. It appears when fx-entry-exit writes one.</Empty>
      </Panel>
    )
  const d = Math.max(decimalsFor(plan.entry), decimalsFor(plan.stop), 2)
  const levels = [
    ...plan.targets.map((t, i) => ({ key: `tp${i + 1}`, label: `TP${i + 1}`, price: t.price, note: `${t.r}R · ${Math.round(t.weight * 100)}%`, kind: "tp" as const })),
    { key: "entry", label: "Entry", price: plan.entry, note: plan.rule.setup, kind: "entry" as const },
    { key: "stop", label: "Stop", price: plan.stop, note: `${plan.risk_ticks} ticks`, kind: "stop" as const },
  ]
  const all = levels.map((l) => l.price).concat([plan.range.high, plan.range.low].filter((x): x is number => x !== null))
  const hi = Math.max(...all), lo = Math.min(...all)
  const pad = (hi - lo) * 0.08 || 1
  const y = (p: number) => ((hi + pad - p) / (hi - lo + 2 * pad)) * 100
  const long = plan.side === "long"
  return (
    <Panel
      icon={<Crosshair className="size-4 text-brand-blue" />}
      title="Trade plan"
      right={
        <Badge variant="outline" className={cn("gap-1 font-mono", long ? "border-chart-4/50 text-chart-4" : "border-destructive/50 text-destructive")}>
          {long ? <TrendingUp /> : <TrendingDown />} {plan.side.toUpperCase()} {plan.symbol}
        </Badge>
      }
    >
      <div className="grid grid-cols-[1fr_auto] gap-4">
        <div className="relative h-56 rounded-lg border border-border/60 bg-background/40">
          {plan.range.high !== null && plan.range.low !== null && (
            <div
              className="absolute inset-x-0 border-y border-dashed border-brand-blue/40 bg-brand-blue/10"
              style={{ top: `${y(plan.range.high)}%`, height: `${y(plan.range.low) - y(plan.range.high)}%` }}
            >
              <span className="absolute top-0.5 right-1.5 text-[10px] text-brand-blue">{plan.range.name} range</span>
            </div>
          )}
          <div
            className={cn("absolute inset-x-0", long ? "bg-chart-4/10" : "bg-chart-4/10")}
            style={long ? { top: `${y(plan.targets[plan.targets.length - 1].price)}%`, height: `${y(plan.entry) - y(plan.targets[plan.targets.length - 1].price)}%` }
                        : { top: `${y(plan.entry)}%`, height: `${y(plan.targets[plan.targets.length - 1].price) - y(plan.entry)}%` }}
          />
          <div
            className="absolute inset-x-0 bg-destructive/10"
            style={long ? { top: `${y(plan.entry)}%`, height: `${y(plan.stop) - y(plan.entry)}%` } : { top: `${y(plan.stop)}%`, height: `${y(plan.entry) - y(plan.stop)}%` }}
          />
          {levels.map((l) => (
            <div key={l.key} className="absolute inset-x-0 flex -translate-y-1/2 items-center gap-2 px-2" style={{ top: `${y(l.price)}%` }}>
              <div className={cn("h-px flex-1", l.kind === "tp" ? "bg-chart-4" : l.kind === "stop" ? "bg-destructive" : "bg-foreground")} />
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 font-mono text-[11px] font-semibold",
                  l.kind === "tp" ? "bg-chart-4/15 text-chart-4" : l.kind === "stop" ? "bg-destructive/15 text-destructive" : "bg-foreground/10 text-foreground",
                )}
              >
                {l.label} {price(l.price, d)}
              </span>
            </div>
          ))}
        </div>
        <dl className="grid content-start gap-2 text-xs">
          <Stat label="Reward / risk" value={plan.rr.toFixed(2)} />
          <Stat label="Risk per unit" value={price(plan.risk, d)} />
          <Stat label="Stop rule" value={plan.rule.stop} />
          <Stat label="After TP1" value={plan.be_after_tp1 ? "stop → entry" : "stop stays"} />
          <Stat label="Signal" value={clock(plan.signal_t, tz)} />
          <Stat label="Valid until" value={clock(plan.valid_until, tz)} />
          <Stat label="Flat by" value={plan.flat_by ? clock(plan.flat_by, tz) : "—"} />
        </dl>
      </div>
    </Panel>
  )
}

function Stat({ label, value, className }: { label: string; value: ReactNode; className?: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className={cn("font-mono text-sm", className)}>{value}</dd>
    </div>
  )
}

// ---------------------------------------------------------------- time machine

const OUTCOME_COLOR: Record<string, string> = {
  stop: "bg-destructive", tp1: "bg-chart-4/60", tp2: "bg-chart-4/80", tp3: "bg-chart-4", open: "bg-muted-foreground/50",
}

export function OddsCard({ replay }: { replay: ConsoleState["replay"] }) {
  const mc = replay?.monte_carlo
  if (!replay || !mc)
    return (
      <Panel icon={<Rewind className="size-4 text-chart-3" />} title="Time machine">
        <Empty>No replay yet. Run fx-timemachine on the plan.</Empty>
      </Panel>
    )
  const bars = [
    { label: "Stop before TP1", v: mc.outcomes.stop ?? 0, cls: "bg-destructive" },
    ...mc.reached_target.map((v, i) => ({ label: `Reached TP${i + 1}`, v, cls: ["bg-chart-4/60", "bg-chart-4/80", "bg-chart-4"][i] ?? "bg-chart-4" })),
    { label: "Nothing hit", v: mc.outcomes.open ?? 0, cls: "bg-muted-foreground/50" },
  ]
  const h = replay.history
  const tone = replay.verdict?.startsWith("leans positive") ? "text-chart-4 border-chart-4/50" : replay.verdict?.startsWith("leans negative") ? "text-destructive border-destructive/50" : "text-gold border-gold/50"
  return (
    <Panel
      icon={<Rewind className="size-4 text-chart-3" />}
      title="Time machine"
      right={<span className="font-mono text-[11px] text-muted-foreground">{mc.runs.toLocaleString()} runs · seed {mc.seed}</span>}
    >
      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Average result</div>
          <div className={cn("font-mono text-3xl font-semibold", mc.mean_r >= 0 ? "text-chart-4" : "text-destructive")}>
            {mc.mean_r >= 0 ? "+" : ""}{mc.mean_r.toFixed(2)}R
          </div>
          <div className="font-mono text-[11px] text-muted-foreground">5% {mc.p5_r.toFixed(2)}R · 95% +{mc.p95_r.toFixed(2)}R · ahead {pct(mc.win_rate)}</div>
        </div>
        <Badge variant="outline" className={cn("max-w-[55%] text-right whitespace-normal", tone)}>{replay.verdict}</Badge>
      </div>
      <div className="mt-4 grid gap-2">
        {bars.map((b) => (
          <div key={b.label} className="grid grid-cols-[7.5rem_1fr_3.5rem] items-center gap-2 text-xs">
            <span className="text-muted-foreground">{b.label}</span>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div className={cn("h-full rounded-full transition-[width] duration-700", b.cls)} style={{ width: `${Math.max(1, b.v * 100)}%` }} />
            </div>
            <span className="text-right font-mono">{pct(b.v)}</span>
          </div>
        ))}
      </div>
      {h && h.fired !== undefined && (
        <div className="mt-4 border-t border-border/60 pt-3">
          <div className="mb-2 flex justify-between text-[11px] text-muted-foreground">
            <span>Same rule on {h.sessions} real sessions: fired {h.fired}×</span>
            <span className="font-mono">{h.mean_r !== undefined && h.mean_r !== null ? `${h.mean_r >= 0 ? "+" : ""}${h.mean_r.toFixed(2)}R avg` : ""}</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {replay.trades.map((t, i) => (
              <span key={i} title={`${t.day} ${t.side} ${t.outcome} ${t.r}R`} className={cn("size-3 rounded-[3px]", OUTCOME_COLOR[t.outcome] ?? "bg-muted")} />
            ))}
          </div>
        </div>
      )}
    </Panel>
  )
}

// ---------------------------------------------------------------- risk gate + tickets

export function RiskCard({ state }: { state: ConsoleState }) {
  const o = state.orders[0]
  if (!o)
    return (
      <Panel icon={<ShieldCheck className="size-4 text-chart-5" />} title="Risk gate">
        <Empty>No order sized yet. fx-risk size.py writes one.</Empty>
      </Panel>
    )
  const v = o.verdict
  const pass = v?.verdict === "PASS"
  const statusTone: Record<string, string> = {
    READY: "border-teal/60 text-teal", BLOCKED: "border-destructive/60 text-destructive", UNCHECKED: "border-border text-muted-foreground",
    APPROVED: "border-gold/60 text-gold", SENT: "border-chart-4/60 text-chart-4",
  }
  return (
    <Panel
      icon={<ShieldCheck className="size-4 text-chart-5" />}
      title="Risk gate"
      right={<Badge variant="outline" className={cn("font-mono", statusTone[o.status])}>{o.status}</Badge>}
    >
      <div className="flex items-center gap-3">
        <div className={cn("grid size-14 shrink-0 place-items-center rounded-2xl border-2",
          !v ? "border-border text-muted-foreground" : pass ? "border-chart-4/60 bg-chart-4/10 text-chart-4" : "border-destructive/60 bg-destructive/10 text-destructive")}>
          {!v ? <Gauge className="size-6" /> : pass ? <Check className="size-7" /> : <X className="size-7" />}
        </div>
        <div className="min-w-0">
          <div className="font-mono text-sm font-semibold">
            {o.kind === "close" ? "CLOSE" : o.side === "long" ? "BUY" : "SELL"} {o.qty} {o.broker_symbol ?? o.symbol}
          </div>
          <div className="text-xs text-muted-foreground">
            {o.legs.length} leg{o.legs.length === 1 ? "" : "s"} · max loss {money(o.max_loss, o.account_ccy)} · R/R {o.rr?.toFixed(2)} · {o.paper ? "paper/demo" : "LIVE"} via {o.broker}
          </div>
        </div>
      </div>
      <ul className="mt-3 grid gap-1.5 text-xs">
        {(v?.reasons ?? []).map((r, i) => (
          <li key={"r" + i} className="flex gap-2 text-destructive"><X className="mt-0.5 size-3.5 shrink-0" />{r}</li>
        ))}
        {(v?.warnings ?? []).map((w, i) => (
          <li key={"w" + i} className="flex gap-2 text-gold"><TriangleAlert className="mt-0.5 size-3.5 shrink-0" />{w}</li>
        ))}
        {pass && v?.reasons.length === 0 && (
          <li className="flex gap-2 text-chart-4"><Check className="mt-0.5 size-3.5 shrink-0" />Every limit passed for this exact order.</li>
        )}
      </ul>
      {o.status === "READY" && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-teal/40 bg-teal/10 p-2.5 text-xs text-teal">
          <Hand className="mt-0.5 size-4 shrink-0" />
          Waiting for your yes in the chat. This console cannot approve or send orders.
        </div>
      )}
    </Panel>
  )
}

export function TodayCard({ state }: { state: ConsoleState }) {
  const { today, config } = state
  const used = Math.max(0, -today.realized) + today.open_risk
  const lim = today.daily_limit
  const share = lim ? Math.min(1, used / lim) : 0
  return (
    <Panel icon={<Wallet className="size-4 text-teal" />} title="Today"
      right={<span className="font-mono text-[11px] text-muted-foreground">{money(config.balance, config.ccy)}</span>}>
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Realized" value={money(today.realized, config.ccy)} className={today.realized >= 0 ? "text-chart-4" : "text-destructive"} />
        <Stat label="Open risk" value={money(today.open_risk, config.ccy)} />
        <Stat label="Trades" value={`${today.trades} / ${config.max_trades ?? "∞"}`} />
      </div>
      <div className="mt-4">
        <div className="mb-1 flex justify-between text-[11px] text-muted-foreground">
          <span>Daily loss limit used</span>
          <span className="font-mono">{money(used, config.ccy)} of {money(lim, config.ccy)}</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-muted">
          <div className={cn("h-full rounded-full transition-[width] duration-700", share > 0.8 ? "bg-destructive" : share > 0.5 ? "bg-gold" : "bg-teal")} style={{ width: `${share * 100}%` }} />
        </div>
      </div>
      <div className="mt-4 grid gap-1.5">
        {state.positions.length === 0 && <p className="text-xs text-muted-foreground">No trades recorded yet.</p>}
        {state.positions.slice(0, 5).map((p) => (
          <div key={p.order_id} className="flex items-center justify-between rounded-md border border-border/60 px-2.5 py-1.5 text-xs">
            <span className="font-mono">{p.symbol} <span className="text-muted-foreground">{p.side}</span></span>
            <span className={cn("rounded-full px-2 py-0.5 text-[10px] uppercase",
              p.status === "open" ? "bg-teal/15 text-teal" : p.status === "closed" ? "bg-muted text-muted-foreground" : "bg-gold/15 text-gold")}>{p.status}</span>
            <span className={cn("font-mono", p.pnl >= 0 ? "text-chart-4" : "text-destructive")}>{money(p.pnl, config.ccy)}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

// ---------------------------------------------------------------- scanner + news

const STATE_TONE: Record<string, string> = {
  triggered: "bg-teal/15 text-teal border-teal/40", waiting: "bg-brand-blue/10 text-brand-blue border-brand-blue/40",
  forming: "bg-gold/10 text-gold border-gold/40", expired: "bg-muted text-muted-foreground border-border",
  no_data: "bg-muted text-muted-foreground border-border", filtered: "bg-muted text-muted-foreground border-border",
  waiting_for_range: "bg-muted text-muted-foreground border-border",
}

export function ScanCard({ state }: { state: ConsoleState }) {
  const rows = state.scan.rows
  return (
    <Panel icon={<Radar className="size-4 text-chart-2" />} title="Scanner"
      right={<span className="font-mono text-[11px] text-muted-foreground">{state.scan.at ? clock(state.scan.at, state.config.display_tz) : "—"}</span>}>
      {rows.length === 0 ? <Empty>No scan yet.</Empty> : (
        <div className="-mx-4 overflow-x-auto px-4">
          <table className="w-full min-w-[30rem] text-xs">
            <thead className="text-left text-[10px] uppercase tracking-wide text-muted-foreground">
              <tr><th className="pb-2 font-medium">Symbol</th><th className="pb-2 font-medium">Range</th><th className="pb-2 font-medium">State</th>
                <th className="pb-2 text-right font-medium">Low – high</th><th className="pb-2 text-right font-medium">R/ATR</th><th className="pb-2 text-right font-medium">Trend</th></tr>
            </thead>
            <tbody className="font-mono">
              {rows.map((r, i) => {
                const d = r.range_high ? Math.min(5, Math.max(decimalsFor(r.range_high), 2)) : 2
                return (
                  <tr key={i} className="border-t border-border/40">
                    <td className="py-1.5 font-semibold">{r.symbol}</td>
                    <td className="py-1.5 text-muted-foreground">{r.range} · {r.setup}</td>
                    <td className="py-1.5">
                      <span className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px]", STATE_TONE[r.state] ?? STATE_TONE.no_data)}>
                        {r.state === "triggered" && <span className="size-1.5 rounded-full bg-teal pulse-ring" />}
                        {r.state.replace(/_/g, " ")}{r.side ? ` ${r.side}` : ""}
                      </span>
                    </td>
                    <td className="py-1.5 text-right">{r.range_low !== undefined && r.range_low !== null ? `${price(r.range_low, d)} – ${price(r.range_high, d)}` : "—"}</td>
                    <td className="py-1.5 text-right">{r.range_atr ? `${r.range_atr.toFixed(2)}×` : "—"}</td>
                    <td className={cn("py-1.5 text-right", r.trend === "up" ? "text-chart-4" : r.trend === "down" ? "text-destructive" : "text-muted-foreground")}>{r.trend ?? "—"}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}

function countdown(target: number, now: number) {
  const s = Math.round((target - now) / 1000)
  const a = Math.abs(s)
  const h = Math.floor(a / 3600), m = Math.floor((a % 3600) / 60), sec = a % 60
  const body = h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m ${String(sec).padStart(2, "0")}s`
  return s >= 0 ? `in ${body}` : `${body} ago`
}

export function NewsCard({ state, nowMs }: { state: ConsoleState; nowMs: number }) {
  const ev = state.calendar.upcoming
  return (
    <Panel icon={<CalendarClock className="size-4 text-gold" />} title="News ahead"
      right={<span className="text-[11px] text-muted-foreground">{state.calendar.updated ? `feed ${clock(state.calendar.updated, state.config.display_tz, true)}` : "no feed"}</span>}>
      {ev.length === 0 ? <Empty>No high or medium events in the next 3 days.</Empty> : (
        <ul className="grid gap-2">
          {ev.map((e, i) => {
            const t = new Date(e.t).getTime()
            const soon = Math.abs(t - nowMs) < 15 * 60 * 1000
            return (
              <li key={i} className={cn("flex items-center gap-3 rounded-lg border px-3 py-2", soon ? "border-destructive/60 bg-destructive/10" : "border-border/60")}>
                <span className={cn("size-2 shrink-0 rounded-full", e.impact === "High" ? "bg-destructive" : "bg-gold")} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs font-medium">{e.title}</div>
                  <div className="font-mono text-[10px] text-muted-foreground">{e.country} · {clock(e.t, state.config.display_tz, true)}{e.forecast ? ` · fcst ${e.forecast}` : ""}</div>
                </div>
                <span className={cn("shrink-0 font-mono text-[11px]", soon ? "text-destructive" : "text-muted-foreground")}>{countdown(t, nowMs)}</span>
              </li>
            )
          })}
        </ul>
      )}
    </Panel>
  )
}
