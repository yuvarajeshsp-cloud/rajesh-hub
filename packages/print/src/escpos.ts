// ESC/POS: the command language almost every receipt printer understands.
// Receipts are sent as a picture (raster image) rather than as text, so any
// character — ₹, Tamil, a logo — prints exactly as it looks on screen and no
// printer code page has to match.

const ESC = 0x1b
const GS = 0x1d

/** ESC @ — reset the printer to its defaults. */
export const INIT = Uint8Array.of(ESC, 0x40)

/** ESC d n — feed n lines. */
export function feed(lines: number): Uint8Array {
  return Uint8Array.of(ESC, 0x64, Math.max(0, Math.min(255, lines)))
}

/** GS V 66 0 — feed to the cutter and make a partial cut (ignored if there is none). */
export const CUT = Uint8Array.of(GS, 0x56, 66, 0)

export interface Bitmap {
  /** Width in dots; the printer needs a multiple of 8. */
  width: number
  height: number
  /** 1 = black. Row-major, one byte per dot. */
  dots: Uint8Array
}

/** Turns a canvas into black/white dots. Anything darker than `threshold` prints black. */
export function canvasToBitmap(canvas: HTMLCanvasElement, threshold = 175): Bitmap {
  const width = Math.ceil(canvas.width / 8) * 8
  const height = canvas.height
  const ctx = canvas.getContext("2d")!
  const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height)
  const dots = new Uint8Array(width * height)
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < canvas.width; x++) {
      const i = (y * canvas.width + x) * 4
      const alpha = data[i + 3] / 255
      // Transparent pixels are paper.
      const lum = (0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]) * alpha + 255 * (1 - alpha)
      dots[y * width + x] = lum < threshold ? 1 : 0
    }
  }
  return { width, height, dots }
}

/**
 * GS v 0 raster bit image, sent in strips of `stripHeight` rows. Printers with
 * small buffers drop a single tall image, so the picture goes in pieces.
 */
export function rasterStrips(bitmap: Bitmap, stripHeight = 96): Uint8Array[] {
  const bytesPerRow = bitmap.width / 8
  const out: Uint8Array[] = []
  for (let top = 0; top < bitmap.height; top += stripHeight) {
    const rows = Math.min(stripHeight, bitmap.height - top)
    const buf = new Uint8Array(8 + bytesPerRow * rows)
    buf.set([GS, 0x76, 0x30, 0x00, bytesPerRow & 0xff, (bytesPerRow >> 8) & 0xff, rows & 0xff, (rows >> 8) & 0xff])
    let o = 8
    for (let r = 0; r < rows; r++) {
      const rowStart = (top + r) * bitmap.width
      for (let b = 0; b < bytesPerRow; b++) {
        let byte = 0
        for (let bit = 0; bit < 8; bit++) {
          if (bitmap.dots[rowStart + b * 8 + bit]) byte |= 0x80 >> bit
        }
        buf[o++] = byte
      }
    }
    out.push(buf)
  }
  return out
}

/** A whole receipt: reset, the picture, a few blank lines, then cut. */
export function receiptJob(bitmap: Bitmap, opts: { feedLines?: number; cut?: boolean } = {}): Uint8Array[] {
  const { feedLines = 4, cut = true } = opts
  return [INIT, ...rasterStrips(bitmap), feed(feedLines), ...(cut ? [CUT] : [])]
}
