import { canvasToBitmap, receiptJob } from "./escpos"
import { renderReceipt, type ReceiptBlock } from "./receipt"
import { availableKinds, connectPrinter, PrinterError, type PrinterKind, type Transport } from "./transports"

export { availableKinds, kindLabel, PrinterError, type PrinterKind } from "./transports"

// The printer belongs to the device, not the account: a phone and the shop
// computer each remember their own (in localStorage).

export interface PrinterSettings {
  kind: PrinterKind
  name: string
  ref: Transport["ref"]
  /** Printable dots across the paper: 576 for 80mm, 384 for 58mm. */
  paperDots: 576 | 384
}

let storageKey = "receipt_printer_v1"
/** Use a different key per app if two hub apps run on the same browser origin. */
export function setPrinterStorageKey(key: string) {
  storageKey = key
}

const listeners = new Set<() => void>()
let active: Transport | null = null

function emit() {
  for (const l of listeners) l()
}

export function onPrinterChange(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function getPrinterSettings(): PrinterSettings | null {
  try {
    const raw = localStorage.getItem(storageKey)
    return raw ? (JSON.parse(raw) as PrinterSettings) : null
  } catch {
    return null
  }
}

function save(settings: PrinterSettings) {
  try {
    localStorage.setItem(storageKey, JSON.stringify(settings))
  } catch {
    // storage unavailable — the printer just has to be chosen again next time
  }
  emit()
}

export function setPaperWidth(paperDots: 576 | 384) {
  const current = getPrinterSettings()
  if (current) save({ ...current, paperDots })
  else save({ kind: availableKinds()[0] ?? "usb", name: "", ref: {}, paperDots })
}

export function isPrinterConnected(): boolean {
  return active !== null
}

export async function forgetPrinter() {
  if (active) await active.close().catch(() => {})
  active = null
  try {
    localStorage.removeItem(storageKey)
  } catch {
    // ignore
  }
  emit()
}

/**
 * Asks the system to pick a printer (must follow a tap) and remembers it.
 * `kind` defaults to the best connection this device has.
 */
export async function pairPrinter(kind?: PrinterKind): Promise<PrinterSettings> {
  const chosen = kind ?? availableKinds()[0]
  if (!chosen) {
    throw new PrinterError(
      "This browser can't talk to a printer directly",
      "Use Chrome or Edge on a computer, or the Android / iPhone app.",
    )
  }
  if (active) await active.close().catch(() => {})
  active = null
  const transport = await connectPrinter(chosen)
  active = transport
  const previous = getPrinterSettings()
  const settings: PrinterSettings = {
    kind: transport.kind,
    name: transport.name,
    ref: transport.ref,
    paperDots: previous?.paperDots ?? 576,
  }
  save(settings)
  return settings
}

async function ensureTransport(): Promise<Transport> {
  if (active) return active
  const saved = getPrinterSettings()
  if (saved) {
    try {
      active = await connectPrinter(saved.kind, saved.ref)
      return active
    } catch (err) {
      // A saved Bluetooth printer that's off or out of range lands here; fall
      // through to asking, which also covers a printer that was swapped.
      if (!(err instanceof PrinterError) || saved.kind === "usb") throw err
    }
  }
  await pairPrinter(saved?.kind)
  if (!active) throw new PrinterError("No printer was chosen")
  return active
}

/**
 * Prints any receipt. Pass the blocks, or a promise of them, so the printer
 * connection is made first: choosing a printer needs the tap that started
 * this, and the browser only honours that for a few seconds.
 */
export async function printReceipt(blocks: ReceiptBlock[] | Promise<ReceiptBlock[]>): Promise<void> {
  const transport = await ensureTransport()
  const paperDots = getPrinterSettings()?.paperDots ?? 576
  const canvas = await renderReceipt(await blocks, paperDots)
  const job = receiptJob(canvasToBitmap(canvas))
  try {
    await transport.write(job)
  } catch {
    // The link dropped (printer switched off, moved away). Forget it so the
    // next print reconnects instead of failing the same way.
    active = null
    emit()
    throw new PrinterError(
      "The printer stopped responding",
      "Check that it is on, has paper and is close by, then try again.",
    )
  }
}

/** A short test slip so the connection and paper width can be checked. */
export async function printTestPage(): Promise<void> {
  await printReceipt([
    { t: "text", text: "Printer test", align: "center", size: "big", bold: true },
    { t: "divider" },
    { t: "row", left: "Rupee sign", right: "₹1,234.50" },
    { t: "row", left: "Bold row", right: "OK", bold: true },
    { t: "text", text: "தையல் • Tamil text", size: "normal" },
    { t: "text", text: "If every line is complete and not cut off at the edges, the paper width is right.", size: "small", muted: true },
    { t: "divider" },
  ])
}
