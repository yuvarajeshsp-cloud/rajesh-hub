// A receipt is described once, as a list of blocks, then drawn onto a canvas
// at the printer's dot width. Drawing it ourselves (instead of capturing HTML)
// keeps the output sharp, supports any script the device has a font for, and
// does not depend on the page's styles.

export type ReceiptSize = "small" | "normal" | "big" | "huge"

export type ReceiptBlock =
  | { t: "text"; text: string; align?: "left" | "center" | "right"; size?: ReceiptSize; bold?: boolean; muted?: boolean }
  | { t: "row"; left: string; right: string; size?: ReceiptSize; bold?: boolean; muted?: boolean }
  | { t: "divider" }
  | { t: "space"; h: number }
  | { t: "image"; src: string; maxWidth: number; maxHeight: number }


/** Shop details printed at the top of every receipt. Every field is optional. */
export interface ReceiptHeader {
  name?: string
  tagline?: string
  /** data:image/... URL; printed centred above the name. */
  logoDataUrl?: string
  lines?: string[]
}

/** The standard centred header: logo, name, tagline, then address/phone/GST lines. */
export function headerBlocks(h: ReceiptHeader): ReceiptBlock[] {
  const blocks: ReceiptBlock[] = []
  const logo = (h.logoDataUrl || "").trim()
  if (logo.startsWith("data:image/")) blocks.push({ t: "image", src: logo, maxWidth: 200, maxHeight: 120 })
  if (h.name?.trim()) blocks.push({ t: "text", text: h.name.trim(), align: "center", size: "big", bold: true })
  if (h.tagline?.trim()) blocks.push({ t: "text", text: h.tagline.trim(), align: "center", size: "small", muted: true })
  for (const line of (h.lines || []).map((l) => l.trim()).filter(Boolean)) blocks.push({ t: "text", text: line, align: "center", size: "small" })
  return blocks
}

// --- drawing ---------------------------------------------------------------

const FONT_FAMILY = `system-ui, -apple-system, "Segoe UI", "Noto Sans", "Noto Sans Tamil", "Noto Sans Devanagari", Roboto, Arial, sans-serif`
const SIZE_PX: Record<ReceiptSize, number> = { small: 20, normal: 23, big: 30, huge: 46 }

function loadImage(src: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = src
  })
}

/** Draws blocks onto a white canvas `width` dots wide, as tall as the content needs. */
export async function renderReceipt(blocks: ReceiptBlock[], width = 576): Promise<HTMLCanvasElement> {
  const margin = 10
  const inner = width - margin * 2
  const measure = document.createElement("canvas").getContext("2d")!
  const fontFor = (size: ReceiptSize, bold?: boolean) => `${bold ? "700" : "400"} ${SIZE_PX[size]}px ${FONT_FAMILY}`

  const wrap = (text: string, size: ReceiptSize, bold: boolean | undefined, maxWidth: number): string[] => {
    measure.font = fontFor(size, bold)
    const out: string[] = []
    for (const para of String(text).split("\n")) {
      let line = ""
      for (const word of para.split(/\s+/).filter(Boolean)) {
        const attempt = line ? `${line} ${word}` : word
        if (measure.measureText(attempt).width <= maxWidth || !line) {
          line = attempt
        } else {
          out.push(line)
          line = word
        }
      }
      out.push(line)
    }
    return out
  }

  // Pre-load images so heights are known.
  const images = new Map<number, HTMLImageElement>()
  await Promise.all(
    blocks.map(async (blk, i) => {
      if (blk.t === "image") {
        const img = await loadImage(blk.src)
        if (img) images.set(i, img)
      }
    }),
  )

  const lineHeight = (size: ReceiptSize) => Math.round(SIZE_PX[size] * 1.35)

  // Layout pass.
  let height = 12
  for (const [i, blk] of blocks.entries()) {
    if (blk.t === "text") height += wrap(blk.text, blk.size || "normal", blk.bold, inner).length * lineHeight(blk.size || "normal")
    else if (blk.t === "row") {
      const size = blk.size || "normal"
      measure.font = fontFor(size, blk.bold)
      const rightW = measure.measureText(blk.right).width
      height += wrap(blk.left, size, blk.bold, Math.max(80, inner - rightW - 12)).length * lineHeight(size)
    } else if (blk.t === "divider") height += 18
    else if (blk.t === "space") height += blk.h
    else if (blk.t === "image") {
      const img = images.get(i)
      if (img) height += scaled(img, blk.maxWidth, blk.maxHeight).h + 8
    }
  }
  height += 12

  const canvas = document.createElement("canvas")
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext("2d")!
  ctx.fillStyle = "#fff"
  ctx.fillRect(0, 0, width, height)
  ctx.textBaseline = "top"

  let y = 12
  for (const [i, blk] of blocks.entries()) {
    if (blk.t === "text") {
      const size = blk.size || "normal"
      ctx.font = fontFor(size, blk.bold)
      ctx.fillStyle = blk.muted ? "#333" : "#000"
      for (const line of wrap(blk.text, size, blk.bold, inner)) {
        const w = ctx.measureText(line).width
        const x = blk.align === "center" ? (width - w) / 2 : blk.align === "right" ? width - margin - w : margin
        ctx.fillText(line, x, y)
        y += lineHeight(size)
      }
    } else if (blk.t === "row") {
      const size = blk.size || "normal"
      ctx.font = fontFor(size, blk.bold)
      ctx.fillStyle = blk.muted ? "#333" : "#000"
      const rightW = ctx.measureText(blk.right).width
      const lines = wrap(blk.left, size, blk.bold, Math.max(80, inner - rightW - 12))
      lines.forEach((line, n) => {
        ctx.fillText(line, margin, y + n * lineHeight(size))
      })
      ctx.fillText(blk.right, width - margin - rightW, y)
      y += lines.length * lineHeight(size)
    } else if (blk.t === "divider") {
      ctx.fillStyle = "#000"
      for (let x = margin; x < width - margin; x += 10) ctx.fillRect(x, y + 8, 5, 2)
      y += 18
    } else if (blk.t === "space") {
      y += blk.h
    } else if (blk.t === "image") {
      const img = images.get(i)
      if (img) {
        const { w, h } = scaled(img, blk.maxWidth, blk.maxHeight)
        ctx.drawImage(img, (width - w) / 2, y, w, h)
        y += h + 8
      }
    }
  }
  return canvas
}

function scaled(img: HTMLImageElement, maxW: number, maxH: number) {
  const r = Math.min(maxW / img.width, maxH / img.height, 1)
  return { w: Math.max(1, Math.round(img.width * r)), h: Math.max(1, Math.round(img.height * r)) }
}
