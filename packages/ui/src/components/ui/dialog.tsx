import * as React from "react"
import { ChevronLeft, XIcon } from "lucide-react"
import { Dialog as DialogPrimitive } from "radix-ui"

import { cn } from "../../lib/utils"
import { Button } from "./button"
import { useIsMobile } from "../../hooks/use-mobile"
import { useBrand } from "../../lib/brand"
import { registerOpenDialog } from "../../lib/dialog-stack"

function Dialog({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />
}

function DialogTrigger({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Trigger>) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />
}

function DialogPortal({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Portal>) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />
}

function DialogClose({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Close>) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />
}

function DialogOverlay({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      data-slot="dialog-overlay"
      className={cn(
        "fixed inset-0 z-50 bg-black/50 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0",
        className
      )}
      {...props}
    />
  )
}

const EDGE_PX = 28

/**
 * On phones a dialog is a full page that slides in from the right, like the
 * pages opened from More: the shop's header and a back button stay pinned at
 * the top while the form scrolls beneath, and a swipe from the left edge (or
 * the system back) closes it. On larger screens it stays a centred popup.
 * Pass `fullPage={false}` to keep a small picker as a popup on phones too.
 */
function DialogContent({
  className,
  children,
  showCloseButton = true,
  fullPage = true,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content> & {
  showCloseButton?: boolean
  fullPage?: boolean
}) {
  const isMobile = useIsMobile()
  if (isMobile && fullPage) {
    return <DialogPage {...props}>{children}</DialogPage>
  }
  return (
    <DialogPortal data-slot="dialog-portal">
      <DialogOverlay />
      <DialogPrimitive.Content
        data-slot="dialog-content"
        className={cn(
          "fixed top-[50%] left-[50%] z-50 grid w-full max-w-[calc(100%-2rem)] translate-x-[-50%] translate-y-[-50%] gap-4 rounded-lg border bg-background p-6 shadow-lg duration-200 outline-none data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 sm:max-w-lg",
          className
        )}
        {...props}
      >
        {children}
        {showCloseButton && (
          <DialogPrimitive.Close
            data-slot="dialog-close"
            className="absolute top-4 right-4 rounded-xs opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:outline-hidden disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4"
          >
            <XIcon />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPortal>
  )
}

function DialogPage({
  children,
  ...props
}: Omit<React.ComponentProps<typeof DialogPrimitive.Content>, "className">) {
  const { companyName, companyLogo } = useBrand()
  const pageRef = React.useRef<HTMLDivElement | null>(null)
  const backRef = React.useRef<HTMLButtonElement | null>(null)
  // The dialog's own title is lifted into the pinned header so it stays in
  // view while the form scrolls.
  const [title, setTitle] = React.useState("")
  React.useLayoutEffect(() => {
    const text = pageRef.current?.querySelector('[data-slot="dialog-title"]')?.textContent ?? ""
    setTitle((prev) => (prev === text ? prev : text))
  })

  // Let the system back button/gesture close this page.
  React.useEffect(() => registerOpenDialog(() => backRef.current?.click()), [])

  // Edge-swipe back: the page follows the finger, the page beneath shows
  // through, and letting go past a third of the screen (or a quick flick)
  // closes it.
  const drag = React.useRef<{ x: number; y: number; t: number; active: boolean; dx: number } | null>(null)

  function onTouchStart(e: React.TouchEvent) {
    const t = e.touches[0]
    drag.current = e.touches.length === 1 && t.clientX <= EDGE_PX ? { x: t.clientX, y: t.clientY, t: Date.now(), active: false, dx: 0 } : null
  }
  function onTouchMove(e: React.TouchEvent) {
    const d = drag.current
    const el = pageRef.current
    if (!d || !el) return
    const t = e.touches[0]
    const dx = t.clientX - d.x
    const dy = t.clientY - d.y
    if (!d.active) {
      if (Math.abs(dy) > 10 && Math.abs(dy) > Math.abs(dx)) {
        drag.current = null
        return
      }
      if (dx <= 10) return
      d.active = true
      // The slide-in animation would fight the inline transform.
      el.style.animation = "none"
    }
    d.dx = Math.max(0, dx)
    el.style.transition = "none"
    el.style.transform = `translateX(${d.dx}px)`
  }
  function onTouchEnd() {
    const d = drag.current
    const el = pageRef.current
    drag.current = null
    if (!d || !d.active || !el) return
    const commit = d.dx > window.innerWidth * 0.35 || (d.dx / Math.max(1, Date.now() - d.t) > 0.5 && d.dx > 40)
    el.style.transition = "transform 220ms ease-out"
    el.style.transform = commit ? "translateX(100%)" : "translateX(0)"
    window.setTimeout(() => {
      if (commit) backRef.current?.click()
      else {
        el.style.transition = ""
        el.style.transform = ""
        el.style.animation = ""
      }
    }, 220)
  }

  return (
    <DialogPortal data-slot="dialog-portal">
      <DialogPrimitive.Content
        data-slot="dialog-content"
        data-fullpage="true"
        ref={pageRef}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
        onTouchCancel={onTouchEnd}
        className="group/page fixed inset-0 z-50 flex flex-col bg-background outline-none [touch-action:pan-y] data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right data-[state=closed]:duration-200 data-[state=open]:animate-in data-[state=open]:slide-in-from-right data-[state=open]:duration-300"
        {...props}
      >
        <div className="flex shrink-0 items-center gap-2 border-b bg-background px-2 pb-2 pt-[calc(env(safe-area-inset-top)+0.5rem)]">
          <DialogPrimitive.Close
            ref={backRef}
            data-slot="dialog-close"
            className="flex size-10 shrink-0 items-center justify-center rounded-full text-foreground active:bg-accent"
          >
            <ChevronLeft className="size-6" />
            <span className="sr-only">Back</span>
          </DialogPrimitive.Close>
          <div className="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-md border bg-background">
            <img src={companyLogo || "/favicon.svg"} alt="" className="h-full w-full object-cover" />
          </div>
          <div className="flex min-w-0 flex-col gap-0.5">
            <span className="truncate text-[11px] font-semibold uppercase leading-tight tracking-[0.12em] text-muted-foreground">
              {companyName}
            </span>
            <span className="truncate text-lg font-bold leading-tight tracking-tight">{title}</span>
          </div>
        </div>
        <div className="grid min-h-0 flex-1 content-start gap-4 overflow-y-auto overscroll-contain p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
          {children}
        </div>
      </DialogPrimitive.Content>
    </DialogPortal>
  )
}

function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-header"
      className={cn("flex flex-col gap-2 text-left", className)}
      {...props}
    />
  )
}

function DialogFooter({
  className,
  showCloseButton = false,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  showCloseButton?: boolean
}) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn(
        "flex flex-col-reverse gap-2 sm:flex-row sm:justify-end",
        // Full-page dialogs keep their action buttons pinned to the bottom.
        "group-data-[fullpage=true]/page:sticky group-data-[fullpage=true]/page:bottom-0 group-data-[fullpage=true]/page:z-10 group-data-[fullpage=true]/page:-mx-4 group-data-[fullpage=true]/page:border-t group-data-[fullpage=true]/page:bg-background group-data-[fullpage=true]/page:px-4 group-data-[fullpage=true]/page:pt-3 group-data-[fullpage=true]/page:pb-[calc(env(safe-area-inset-bottom)+0.75rem)]",
        className
      )}
      {...props}
    >
      {children}
      {showCloseButton && (
        <DialogPrimitive.Close asChild>
          <Button variant="outline">Close</Button>
        </DialogPrimitive.Close>
      )}
    </div>
  )
}

function DialogTitle({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn("text-lg leading-none font-semibold group-data-[fullpage=true]/page:sr-only", className)}
      {...props}
    />
  )
}

function DialogDescription({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
}
