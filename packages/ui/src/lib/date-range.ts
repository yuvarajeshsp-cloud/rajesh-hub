import {
  startOfDay,
  endOfDay,
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
  subMonths,
  subWeeks,
  startOfYear,
} from "date-fns"

export type DateRangePreset =
  | "all_time"
  | "today"
  | "this_week"
  | "last_week"
  | "this_month"
  | "last_month"
  | "last_3_months"
  | "this_year"
  | "custom"

export const DATE_RANGE_PRESETS: { key: DateRangePreset; label: string }[] = [
  { key: "all_time", label: "All Time" },
  { key: "today", label: "Daily (Today)" },
  { key: "this_week", label: "Weekly (This Week)" },
  { key: "last_week", label: "Last Week" },
  { key: "this_month", label: "Current Month" },
  { key: "last_month", label: "Last Month" },
  { key: "last_3_months", label: "Last 3 Months" },
  { key: "this_year", label: "Yearly" },
  { key: "custom", label: "Custom Range" },
]

export interface DateRange {
  from: Date
  to: Date
}

export function computeDateRange(
  preset: DateRangePreset,
  customFrom: string,
  customTo: string,
): DateRange {
  const now = new Date()
  switch (preset) {
    case "all_time":
      return { from: new Date(2000, 0, 1), to: endOfDay(now) }
    case "today":
      return { from: startOfDay(now), to: endOfDay(now) }
    case "this_week":
      return { from: startOfWeek(now, { weekStartsOn: 1 }), to: endOfDay(now) }
    case "last_week": {
      const lastWeek = subWeeks(now, 1)
      return { from: startOfWeek(lastWeek, { weekStartsOn: 1 }), to: endOfWeek(lastWeek, { weekStartsOn: 1 }) }
    }
    case "this_month":
      return { from: startOfMonth(now), to: endOfDay(now) }
    case "last_month": {
      const lastMonth = subMonths(now, 1)
      return { from: startOfMonth(lastMonth), to: endOfMonth(lastMonth) }
    }
    case "last_3_months":
      return { from: startOfMonth(subMonths(now, 2)), to: endOfDay(now) }
    case "this_year":
      return { from: startOfYear(now), to: endOfDay(now) }
    case "custom":
      return {
        from: customFrom ? startOfDay(new Date(customFrom)) : startOfMonth(now),
        to: customTo ? endOfDay(new Date(customTo)) : endOfDay(now),
      }
  }
}

export function isWithinRange(dateStr: string, range: DateRange): boolean {
  const d = new Date(dateStr)
  return d >= range.from && d <= range.to
}
