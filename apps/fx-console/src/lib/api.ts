import { useEffect, useRef, useState } from "react"

export type StageId = "scan" | "calendar" | "plan" | "replay" | "risk" | "broker" | "sync"
export type StageStatus = "idle" | "running" | "ok" | "warn" | "waiting" | "fail" | "stalled"

export interface Activity {
  ts: number
  run: string
  stage: string
  ui_stage: StageId
  kind: "start" | "line" | "end"
  msg: string
  rc?: number
  level?: "info" | "ok" | "warn" | "fail"
}

export interface StageState {
  status: StageStatus
  at: number
  started: number
  last: string
  args: string
  run: string
  duration: number
}

export interface Target { r: number; price: number; weight: number }
export interface Plan {
  symbol: string; side: "long" | "short"; entry: number; stop: number; risk: number; risk_ticks: number
  targets: Target[]; be_after_tp1: boolean; rr: number; signal_t: string; valid_until: string
  flat_by: string | null; horizon: string; range: { name: string; high: number | null; low: number | null; day: string }
  rule: { setup: string; stop: string }
}

export interface MonteCarlo {
  runs: number; seed: number; outcomes: Record<string, number>; reached_target: number[]
  mean_r: number; median_r: number; p5_r: number; p95_r: number; win_rate: number
}

export interface Order {
  id: string; kind: "open" | "close"; symbol: string; side: string; qty: number; unit: string; broker: string
  broker_symbol: string | null; paper: boolean; max_loss: number; account_ccy: string; rr: number
  legs: { qty: number; tp: number; r: number }[]; display?: { entry: string; stop: string; tps: string[] }
  why?: string; note?: string; status: "READY" | "BLOCKED" | "UNCHECKED" | "APPROVED" | "SENT"
  verdict: { verdict: "PASS" | "BLOCK"; reasons: string[]; warnings: string[]; checked: string } | null
}

export interface Position {
  order_id: string; symbol: string; side: string; qty_open: number; filled_qty: number
  avg_price: number | null; pnl: number; status: string; max_loss: number | null
}

export interface ScanRow {
  symbol: string; range: string; setup: string; state: string; side?: string; entry?: number
  range_high?: number; range_low?: number; range_atr?: number; trend?: string; trigger_close_t?: number
  source?: string; note?: string; tz?: string; until?: number; last_close?: number
}

export interface ConsoleState {
  now: string; demo: boolean; trader_dir: string
  config: { ccy: string; balance: number; paper: boolean; broker: string; display_tz: string; risk_pct: number | null
            risk_money: number | null; max_trades: number; min_rr: number; watchlist: string[] }
  stages: { id: StageId; label: string; skill: string }[]
  stage_state: Partial<Record<StageId, StageState>>
  scan: { at: string | null; rows: ScanRow[]; errors: string[] }
  calendar: { updated: string | null; upcoming: { title: string; country: string; impact: string; t: string; forecast?: string; previous?: string }[] }
  plan: Plan | null
  replay: { monte_carlo: MonteCarlo | null; history: { fired?: number; sessions?: number; mean_r?: number; win_rate?: number; outcomes?: Record<string, number>; same_side?: number }
            trades: { day: string; side: string; outcome: string; r: number }[]; verdict: string; at: string; symbol: string } | null
  orders: Order[]
  today: { realized: number; open_risk: number; trades: number; daily_limit: number | null }
  positions: Position[]
  ledger: { ts: string; kind: string; order_id?: string; symbol?: string; pnl?: number; qty?: number; reply?: string }[]
}

const MAX_LINES = 800

export function useConsole() {
  const [state, setState] = useState<ConsoleState | null>(null)
  const [lines, setLines] = useState<Activity[]>([])
  const [live, setLive] = useState<"connecting" | "live" | "offline">("connecting")
  const retry = useRef(0)

  useEffect(() => {
    let es: EventSource | null = null
    let timer: number | undefined
    let closed = false

    const connect = () => {
      setLive("connecting")
      es = new EventSource("/api/events")
      es.addEventListener("open", () => { retry.current = 0; setLive("live") })
      es.addEventListener("backlog", (e) => setLines(JSON.parse((e as MessageEvent).data)))
      es.addEventListener("activity", (e) => {
        const add: Activity[] = JSON.parse((e as MessageEvent).data)
        setLines((prev) => {
          const next = prev.concat(add)
          return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next
        })
      })
      es.addEventListener("state", (e) => setState(JSON.parse((e as MessageEvent).data)))
      es.onerror = () => {
        setLive("offline")
        es?.close()
        if (!closed) {
          const wait = Math.min(10000, 1000 * 2 ** retry.current++)
          timer = window.setTimeout(connect, wait)
        }
      }
    }
    connect()
    return () => { closed = true; es?.close(); window.clearTimeout(timer) }
  }, [])

  return { state, lines, live }
}

export async function runAction(action: string, args: Record<string, string> = {}) {
  const res = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-FX-Console": "1" },
    body: JSON.stringify({ action, args }),
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.error || res.statusText)
  return body
}

// ---------------------------------------------------------------- formatting

export function money(v: number | null | undefined, ccy: string) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—"
  const sym: Record<string, string> = { USD: "$", INR: "₹", EUR: "€", GBP: "£", JPY: "¥" }
  const s = Math.abs(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return (v < 0 ? "−" : "") + (sym[ccy] ?? ccy + " ") + s
}

export function decimalsFor(n: number) {
  const s = String(n)
  return s.includes(".") ? Math.min(5, s.split(".")[1].length) : 0
}

export function price(v: number | null | undefined, digits = 2) {
  return v === null || v === undefined ? "—" : v.toFixed(digits)
}

export function clock(t: number | string | Date, tz: string, withDate = false) {
  const d = typeof t === "number" ? new Date(t * 1000) : new Date(t)
  return d.toLocaleString("en-GB", {
    timeZone: tz, hour: "2-digit", minute: "2-digit", hour12: false,
    ...(withDate ? { day: "2-digit", month: "short" } : {}),
  })
}

export function ago(ts: number, nowMs = Date.now()) {
  const s = Math.max(0, Math.round(nowMs / 1000 - ts))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

export function pct(v: number | undefined | null) {
  return v === undefined || v === null ? "—" : `${(v * 100).toFixed(1)}%`
}
