import { useEffect, useMemo, useRef, useState } from "react"
import { Activity as ActivityIcon, CalendarClock, LoaderCircle, Radar, RefreshCw, Rewind, ShieldCheck, Wifi, WifiOff } from "lucide-react"
import { Badge, Button, ModeToggle, Toaster, cn } from "@rajesh-hub/ui"
import { toast } from "sonner"
import { clock, money, runAction, useConsole } from "./lib/api"
import { Pipeline } from "./components/pipeline"
import { Terminal } from "./components/terminal"
import { NewsCard, OddsCard, PlanCard, RiskCard, ScanCard, TodayCard } from "./components/panels"

const ZONES = [
  { tz: "Asia/Kolkata", label: "IST" },
  { tz: "Europe/London", label: "LDN" },
  { tz: "America/New_York", label: "NY" },
]

// Read-only stages the console may start. Approving, sending and flattening
// orders are not here on purpose: those stay in the chat, behind your yes.
const ACTIONS = [
  { id: "scan", label: "Scan", icon: Radar },
  { id: "calendar", label: "Calendar", icon: CalendarClock },
  { id: "replay", label: "Replay", icon: Rewind },
  { id: "check", label: "Risk check", icon: ShieldCheck },
  { id: "sync", label: "Sync", icon: RefreshCw },
]

function useServerClock(serverNow: string | undefined) {
  const offset = useRef(0)
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    if (serverNow) offset.current = Date.parse(serverNow) - Date.now()
  }, [serverNow])
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [])
  return { market: now + offset.current, wall: now }
}

export default function App() {
  const { state, lines, live } = useConsole()
  const { market, wall } = useServerClock(state?.now)
  const [busy, setBusy] = useState<string | null>(null)

  const running = useMemo(() => {
    const s = new Set<string>()
    for (const [k, v] of Object.entries(state?.stage_state ?? {})) if (v?.status === "running") s.add(k)
    return s
  }, [state])

  async function go(id: string, label: string) {
    setBusy(id)
    try {
      await runAction(id)
      toast.success(`${label} started`, { description: "Watch it in Backend activity." })
    } catch (e) {
      toast.error(`${label} did not start`, { description: (e as Error).message })
    } finally {
      window.setTimeout(() => setBusy(null), 800)
    }
  }

  return (
    <div className="console-bg min-h-svh text-foreground">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-4 px-4 py-4 md:px-6">
        <header className="flex flex-wrap items-center gap-x-4 gap-y-3">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-xl border border-teal/50 bg-teal/10 text-teal">
              <ActivityIcon className="size-5" />
            </span>
            <div>
              <h1 className="text-lg leading-tight font-semibold tracking-tight">Trading Console</h1>
              <p className="text-[11px] text-muted-foreground">fx-futures-trader · what the backend is doing, live</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className={cn("gap-1.5", live === "live" ? "border-chart-4/50 text-chart-4" : live === "offline" ? "border-destructive/50 text-destructive" : "border-gold/50 text-gold")}>
              {live === "live" ? <Wifi /> : live === "offline" ? <WifiOff /> : <LoaderCircle className="animate-spin" />}
              {live === "live" ? "live" : live === "offline" ? "reconnecting" : "connecting"}
            </Badge>
            {state?.demo && <Badge variant="outline" className="border-gold/60 bg-gold/10 text-gold">DEMO data</Badge>}
            {state && (
              <Badge variant="outline" className={state.config.paper ? "border-teal/50 text-teal" : "border-destructive/60 bg-destructive/10 text-destructive"}>
                {state.config.paper ? "PAPER / DEMO" : "LIVE ACCOUNT"}
              </Badge>
            )}
            {state && <Badge variant="outline" className="font-mono">{state.config.broker} · {money(state.config.balance, state.config.ccy)}</Badge>}
          </div>
          <div className="ml-auto flex items-center gap-3">
            <div className="hidden gap-3 font-mono text-xs sm:flex">
              {ZONES.map((z) => (
                <div key={z.tz} className="text-right">
                  <div className="text-[10px] text-muted-foreground">{z.label}</div>
                  <div className="tabular-nums">{clock(Math.floor(market / 1000), z.tz)}</div>
                </div>
              ))}
            </div>
            <ModeToggle />
          </div>
        </header>

        {!state ? (
          <div className="grid min-h-[60svh] place-items-center text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <LoaderCircle className="size-4 animate-spin text-teal" />
              {live === "offline" ? "Can't reach the console server. Start it with: python3 server.py" : "Connecting to the console server…"}
            </div>
          </div>
        ) : (
          <>
            <section aria-label="Pipeline">
              <Pipeline state={state} nowMs={wall} />
            </section>

            <div className="flex flex-wrap items-center gap-2">
              {ACTIONS.map((a) => (
                <Button key={a.id} size="sm" variant="outline" disabled={busy === a.id} onClick={() => go(a.id, a.label)} className="gap-1.5">
                  {busy === a.id ? <LoaderCircle className="animate-spin" /> : <a.icon />} {a.label}
                </Button>
              ))}
              <span className="text-[11px] text-muted-foreground">
                Read-only runs. Orders are approved and sent only in the chat.
              </span>
            </div>

            <main className="grid gap-4 lg:grid-cols-12 [&>*]:min-w-0">
              <div className="lg:col-span-5 lg:row-span-2">
                <Terminal lines={lines} running={running} />
              </div>
              <div className="grid gap-4 lg:col-span-7 xl:grid-cols-2 [&>*]:min-w-0">
                <PlanCard plan={state.plan} tz={state.config.display_tz} />
                <OddsCard replay={state.replay} />
              </div>
              <div className="grid gap-4 lg:col-span-7 xl:grid-cols-2 [&>*]:min-w-0">
                <RiskCard state={state} />
                <TodayCard state={state} />
              </div>
              <div className="lg:col-span-7">
                <ScanCard state={state} />
              </div>
              <div className="lg:col-span-5">
                <NewsCard state={state} nowMs={market} />
              </div>
            </main>

            <footer className="pb-2 text-[11px] text-muted-foreground">
              Watching <span className="font-mono">{state.trader_dir}</span>. Not financial advice; the time machine is a resampling of recent bars, not a forecast.
            </footer>
          </>
        )}
      </div>
      <Toaster />
    </div>
  )
}
