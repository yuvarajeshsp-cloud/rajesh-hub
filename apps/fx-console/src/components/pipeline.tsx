import { CalendarClock, Crosshair, Radar, RefreshCw, Rewind, Send, ShieldCheck, type LucideIcon } from "lucide-react"
import { cn } from "@rajesh-hub/ui"
import { ago, type ConsoleState, type StageId, type StageStatus } from "../lib/api"

const ICONS: Record<StageId, LucideIcon> = {
  scan: Radar, calendar: CalendarClock, plan: Crosshair, replay: Rewind, risk: ShieldCheck, broker: Send, sync: RefreshCw,
}

export const STATUS_STYLE: Record<StageStatus, { text: string; border: string; bg: string; label: string }> = {
  idle: { text: "text-muted-foreground", border: "border-border", bg: "bg-muted/30", label: "idle" },
  running: { text: "text-teal", border: "border-teal/70", bg: "bg-teal/10", label: "running" },
  ok: { text: "text-chart-4", border: "border-chart-4/40", bg: "bg-chart-4/5", label: "done" },
  warn: { text: "text-gold", border: "border-gold/50", bg: "bg-gold/5", label: "done, with notes" },
  waiting: { text: "text-brand-blue", border: "border-brand-blue/50", bg: "bg-brand-blue/5", label: "waiting" },
  fail: { text: "text-destructive", border: "border-destructive/60", bg: "bg-destructive/10", label: "blocked / failed" },
  stalled: { text: "text-muted-foreground", border: "border-border", bg: "bg-muted/30", label: "no end recorded" },
}

export const STAGE_TEXT: Record<StageId, string> = {
  scan: "text-chart-2", calendar: "text-gold", plan: "text-brand-blue", replay: "text-chart-3",
  risk: "text-chart-5", broker: "text-teal", sync: "text-chart-4",
}

function Connector({ active, done }: { active: boolean; done: boolean }) {
  return (
    <svg className="hidden h-6 w-full min-w-6 md:block" viewBox="0 0 60 24" preserveAspectRatio="none" aria-hidden>
      <line x1="0" y1="12" x2="60" y2="12" className={cn("stroke-border", done && "stroke-chart-4/50")} strokeWidth="2" />
      {active && <line x1="0" y1="12" x2="60" y2="12" className="flow-line stroke-teal" strokeWidth="2" />}
      <path d="M54 7 L60 12 L54 17" fill="none" className={cn("stroke-border", (active || done) && "stroke-teal/70")} strokeWidth="2" />
    </svg>
  )
}

export function Pipeline({ state, nowMs }: { state: ConsoleState; nowMs: number }) {
  const ss = state.stage_state
  const running = state.stages.findIndex((s) => ss[s.id]?.status === "running")
  return (
    <div className="-mx-4 overflow-x-auto px-4 pb-1 md:mx-0 md:overflow-visible md:px-0">
      <ol className="flex min-w-max items-stretch gap-2 md:grid md:min-w-0 md:grid-cols-[minmax(0,1fr)_1.75rem_minmax(0,1fr)_1.75rem_minmax(0,1fr)_1.75rem_minmax(0,1fr)_1.75rem_minmax(0,1fr)_1.75rem_minmax(0,1fr)_1.75rem_minmax(0,1fr)] md:gap-0">
        {state.stages.map((s, i) => {
          const st = ss[s.id]
          const status: StageStatus = st?.status ?? "idle"
          const sty = STATUS_STYLE[status]
          const Icon = ICONS[s.id]
          const isRun = status === "running"
          return (
            <li key={s.id} className="contents">
              {i > 0 && (
                <div className="hidden items-center md:flex">
                  <Connector active={running === i || (running === -1 ? false : running > i)} done={!!st && status !== "idle"} />
                </div>
              )}
              <div
                className={cn(
                  "relative flex w-40 flex-col gap-1.5 overflow-hidden rounded-xl border p-3 transition-colors md:w-auto",
                  sty.border, sty.bg, isRun && "scan-sweep",
                )}
              >
                <div className="flex items-center gap-2">
                  <span className={cn("relative grid size-8 place-items-center rounded-full border bg-card", sty.border, sty.text, isRun && "pulse-ring")}>
                    <Icon className={cn("size-4", isRun && s.id === "sync" && "animate-spin")} />
                  </span>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold leading-tight">{s.label}</div>
                    <div className={cn("text-[11px] font-medium uppercase tracking-wide", sty.text)}>{sty.label}</div>
                  </div>
                </div>
                <p className="line-clamp-2 min-h-8 font-mono text-[11px] leading-4 text-muted-foreground" title={st?.last}>
                  {st?.last?.trim() || (isRun ? `▸ ${s.id} ${st?.args ?? ""}` : st ? "finished, no output" : "not run yet")}
                </p>
                <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                  <span>{st ? ago(st.at, nowMs) : "—"}</span>
                  <span className="font-mono">{st ? `${st.duration.toFixed(1)}s` : ""}</span>
                </div>
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
