// Full-page dialogs on mobile (see components/ui/dialog.tsx) register here
// while open, so the Android back button/gesture closes the top one instead of
// leaving the page underneath, and the page's own edge-swipe stays out of the way.

const closers: Array<() => void> = []

export function registerOpenDialog(close: () => void): () => void {
  closers.push(close)
  return () => {
    const i = closers.lastIndexOf(close)
    if (i >= 0) closers.splice(i, 1)
  }
}

/** Closes the top-most open full-page dialog. Returns false when none is open. */
export function closeTopDialog(): boolean {
  const close = closers[closers.length - 1]
  if (!close) return false
  close()
  return true
}

export function hasOpenDialog(): boolean {
  return closers.length > 0
}
