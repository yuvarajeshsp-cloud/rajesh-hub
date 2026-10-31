import { useEffect, useMemo, useRef, useState } from "react"
import { SquareTerminal } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, cn } from "@rajesh-hub/ui"
import type { Activity, StageId } from "../lib/api"
import { STAGE_TEXT } from "./pipeline"

const LEVEL_TEXT: Record<string, string> = {
  info: "text-foreground/80", ok: "text-chart-4", warn: "text-gold", fail: "text-destructive",
}

const FILTERS: (StageId | "all")[] = ["all", "scan", "calendar", "plan", "replay", "risk", "broker", "sync"]

function hhmmss(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString("en-GB", { hour12: false })
}

export function Terminal({ lines, running }: { lines: Activity[]; running: Set<string> }) {
  const [filter, setFilter] = useState<StageId | "all">("all")
  const [stick, setStick] = useState(true)
  const box = useRef<HTMLDivElement>(null)
  const shown = useMemo(() => (filter === "all" ? lines : lines.filter((l) => l.ui_stage === filter)), [lines, filter])

  useEffect(() => {
    if (stick && box.current) box.current.scrollTop = box.current.scrollHeight
  }, [shown, stick])

  return (
    <Card className="flex h-full min-h-[22rem] flex-col gap-0 overflow-hidden border-border/70 bg-card/80 py-0 backdrop-blur">
      <CardHeader className="flex flex-row items-center justify-between gap-2 border-b border-border/60 px-4 py-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <SquareTerminal className="size-4 text-teal" /> Backend activity
        </CardTitle>
        <div className="flex max-w-[65%] gap-1 overflow-x-auto">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "shrink-0 rounded-full border px-2 py-0.5 text-[11px] capitalize transition-colors",
                filter === f ? "border-teal/60 bg-teal/15 text-teal" : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="relative min-h-0 flex-1 p-0">
        <div
          ref={box}
          onScroll={(e) => {
            const el = e.currentTarget
            setStick(el.scrollHeight - el.scrollTop - el.clientHeight < 24)
          }}
          className="grid-lines absolute inset-0 overflow-y-auto px-3 py-2 font-mono text-[11.5px] leading-[1.55]"
        >
          {shown.length === 0 && <div className="py-8 text-center text-muted-foreground">Waiting for the first skill to run…</div>}
          {shown.map((l, i) => {
            const tag = STAGE_TEXT[l.ui_stage] ?? "text-muted-foreground"
            if (l.kind === "start")
              return (
                <div key={i} className="rise mt-2 flex gap-2 border-t border-border/40 pt-2 first:mt-0 first:border-0 first:pt-0">
                  <span className="shrink-0 text-muted-foreground">{hhmmss(l.ts)}</span>
                  <span className={cn("shrink-0 font-semibold", tag)}>▸ {l.stage}</span>
                  <span className="truncate text-muted-foreground">{l.msg}</span>
                </div>
              )
            if (l.kind === "end")
              return (
                <div key={i} className="flex gap-2 text-[10.5px] text-muted-foreground">
                  <span className="shrink-0">{hhmmss(l.ts)}</span>
                  <span className={cn(l.rc === 0 ? "text-chart-4" : l.rc === 3 ? "text-brand-blue" : "text-destructive")}>
                    ■ {l.stage} finished {l.rc === 0 ? "ok" : l.rc === 3 ? "(nothing triggered)" : `with code ${l.rc}`}
                  </span>
                </div>
              )
            return (
              <div key={i} className="flex gap-2">
                <span className="shrink-0 select-none text-muted-foreground/50">{hhmmss(l.ts)}</span>
                <span className={cn("whitespace-pre-wrap break-words", LEVEL_TEXT[l.level ?? "info"])}>{l.msg}</span>
              </div>
            )
          })}
          {running.size > 0 && <div className="caret mt-1 text-teal">{[...running].join(", ")} running</div>}
        </div>
        {!stick && (
          <button
            onClick={() => setStick(true)}
            className="absolute right-3 bottom-3 rounded-full border border-teal/50 bg-card px-3 py-1 text-xs text-teal shadow"
          >
            Jump to latest
          </button>
        )}
      </CardContent>
    </Card>
  )
}
