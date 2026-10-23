import * as React from "react"

import { cn } from "../lib/utils"

export interface BottomNavItem {
  key: string
  label: string
  icon: React.ComponentType<{ className?: string }>
}

// The selected tab is cut out of the bar in the page's own colour, with
// rounded bottom corners and softened shoulders where it meets the bar's top
// edge, so the page appears to flow down into the bar.
const FILLET = 14

type Edge = "first" | "last" | undefined

// On the outermost tabs the cut-out runs flush to the screen edge, with no
// shoulder on that side, so nothing pokes out past the bar's own corner.
function ActiveNotch({ edge }: { edge: Edge }) {
  const fillet = (side: "left" | "right") => (
    <span
      aria-hidden
      className="pointer-events-none absolute -top-px"
      style={{
        width: FILLET,
        height: FILLET + 1,
        [side]: 6 - FILLET,
        background: `radial-gradient(circle at ${side === "left" ? "0" : "100%"} 100%, transparent ${FILLET}px, var(--background) ${FILLET + 0.5}px)`,
      }}
    />
  )
  return (
    <>
      <span
        aria-hidden
        className="pointer-events-none absolute -top-px bottom-2 rounded-b-[22px] bg-background"
        style={{ left: edge === "first" ? 0 : 6, right: edge === "last" ? 0 : 6 }}
      />
      {edge !== "first" && fillet("left")}
      {edge !== "last" && fillet("right")}
    </>
  )
}

function Tab({
  item,
  active,
  edge,
  onClick,
}: {
  item: BottomNavItem
  active: boolean
  edge?: Edge
  onClick: () => void
}) {
  const Icon = item.icon
  return (
    <button
      type="button"
      data-slot="bottom-nav-tab"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "relative flex flex-1 flex-col items-center justify-center gap-1 pb-2 text-[11px] transition-colors",
        active ? "font-semibold text-foreground" : "text-sidebar-foreground/75",
      )}
    >
      {active && <ActiveNotch edge={edge} />}
      <Icon className={cn("relative size-5", active && "text-sidebar-primary")} />
      <span className="relative">{item.label}</span>
    </button>
  )
}

/**
 * Mobile bottom tab bar (from Embroidery-Shop-Manager). Routing stays in the
 * app: pass the tabs, the key of the active one and a select handler.
 * The bar is 4rem tall plus the bottom safe-area inset.
 */
export function BottomNav({
  items,
  active,
  onSelect,
  className,
}: {
  items: BottomNavItem[]
  active: string
  onSelect: (key: string) => void
  className?: string
}) {
  return (
    <nav
      className={cn(
        "fixed inset-x-0 bottom-0 z-50 flex h-[calc(4rem+env(safe-area-inset-bottom))] items-stretch rounded-t-[28px] border-t border-sidebar-border bg-sidebar pb-[env(safe-area-inset-bottom)]",
        className,
      )}
    >
      {items.map((item, index) => (
        <Tab
          key={item.key}
          item={item}
          edge={index === 0 ? "first" : index === items.length - 1 ? "last" : undefined}
          active={item.key === active}
          onClick={() => onSelect(item.key)}
        />
      ))}
    </nav>
  )
}
