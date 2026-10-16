import { Capacitor } from "@capacitor/core"
import { BleClient, numbersToDataView } from "@capacitor-community/bluetooth-le"

// How bytes get to the printer. Three ways, picked by where the app runs:
//   usb         – a printer plugged into a computer (WebUSB, Chrome/Edge)
//   web-ble     – Bluetooth Low Energy from a desktop/Android browser
//   native-ble  – Bluetooth Low Energy from the Android / iPhone app
// Everything below this file only sees a Transport.

export type PrinterKind = "usb" | "web-ble" | "native-ble"

export interface Transport {
  kind: PrinterKind
  /** Human name shown in settings. */
  name: string
  /** Id needed to find the same printer again without asking. */
  ref: { id?: string; vendorId?: number; productId?: number }
  write(chunks: Uint8Array[]): Promise<void>
  close(): Promise<void>
}

export class PrinterError extends Error {
  /** A short, user-facing explanation. */
  hint?: string
  constructor(message: string, hint?: string) {
    super(message)
    this.hint = hint
  }
}

// Service UUIDs that cheap Bluetooth receipt printers commonly use for their
// data pipe. A printer's service has to be listed up front, or the browser
// will not let the page read it.
const KNOWN_SERVICES = [
  "000018f0-0000-1000-8000-00805f9b34fb",
  "0000ff00-0000-1000-8000-00805f9b34fb",
  "0000ffe0-0000-1000-8000-00805f9b34fb",
  "0000fee7-0000-1000-8000-00805f9b34fb",
  "0000ae30-0000-1000-8000-00805f9b34fb",
  "49535343-fe7d-4ae5-8fa9-9fafd205e455",
  "e7810a71-73ae-499d-8c15-faa9aef0c3f2",
  "6e400001-b5a3-f393-8afe-0f6c2c2c0b5c",
  "00001101-0000-1000-8000-00805f9b34fb",
]

const BLE_CHUNK = 100
const BLE_GAP_MS = 12
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

function concat(chunks: Uint8Array[]): Uint8Array {
  const total = chunks.reduce((n, c) => n + c.length, 0)
  const out = new Uint8Array(total)
  let o = 0
  for (const c of chunks) {
    out.set(c, o)
    o += c.length
  }
  return out
}

// ---- WebUSB ---------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyDevice = any

export function usbSupported(): boolean {
  return typeof navigator !== "undefined" && !!(navigator as AnyDevice).usb && !Capacitor.isNativePlatform()
}

async function openUsb(device: AnyDevice): Promise<Transport> {
  try {
    await device.open()
    if (device.configuration === null) await device.selectConfiguration(1)
    let best: { iface: number; alt: number; ep: number; printerClass: boolean } | null = null
    for (const iface of device.configuration.interfaces) {
      for (const alt of iface.alternates) {
        for (const ep of alt.endpoints) {
          if (ep.direction === "out" && ep.type === "bulk") {
            const candidate = {
              iface: iface.interfaceNumber,
              alt: alt.alternateSetting,
              ep: ep.endpointNumber,
              printerClass: alt.interfaceClass === 7,
            }
            if (!best || (candidate.printerClass && !best.printerClass)) best = candidate
          }
        }
      }
    }
    if (!best) throw new PrinterError("This USB device has no printing channel", "Check that the cable is plugged into the printer.")
    await device.claimInterface(best.iface)
    if (best.alt) await device.selectAlternateInterface(best.iface, best.alt)
    const { iface, ep } = best
    return {
      kind: "usb",
      name: device.productName || "USB printer",
      ref: { vendorId: device.vendorId, productId: device.productId },
      async write(chunks) {
        const data = concat(chunks)
        for (let i = 0; i < data.length; i += 16384) {
          await device.transferOut(ep, data.slice(i, i + 16384))
        }
      },
      async close() {
        try {
          await device.releaseInterface(iface)
          await device.close()
        } catch {
          // already gone
        }
      },
    }
  } catch (err) {
    if (err instanceof PrinterError) throw err
    throw new PrinterError(
      "The computer wouldn't give this app access to the printer",
      "On Windows the printer's own driver has to be swapped for a generic USB (WinUSB) driver once — or use \"Print with the browser\" instead.",
    )
  }
}

async function connectUsb(ref?: Transport["ref"]): Promise<Transport> {
  const usb = (navigator as AnyDevice).usb
  if (ref?.vendorId != null) {
    const known: AnyDevice[] = await usb.getDevices()
    const match = known.find((d) => d.vendorId === ref.vendorId && d.productId === ref.productId)
    if (match) return openUsb(match)
    throw new PrinterError("The USB printer isn't connected", "Plug it in and turn it on.")
  }
  const device = await usb.requestDevice({ filters: [] })
  return openUsb(device)
}

// ---- Web Bluetooth ---------------------------------------------------------

export function webBleSupported(): boolean {
  return typeof navigator !== "undefined" && !!(navigator as AnyDevice).bluetooth && !Capacitor.isNativePlatform()
}

async function findWritableWeb(server: AnyDevice): Promise<AnyDevice> {
  const services: AnyDevice[] = await server.getPrimaryServices()
  let fallback: AnyDevice = null
  for (const service of services) {
    const chars: AnyDevice[] = await service.getCharacteristics()
    for (const c of chars) {
      if (c.properties.writeWithoutResponse || c.properties.write) {
        if (KNOWN_SERVICES.includes(service.uuid)) return c
        fallback = fallback || c
      }
    }
  }
  if (fallback) return fallback
  throw new PrinterError("This Bluetooth device doesn't accept print data", "It may be a classic-Bluetooth-only printer, which a browser can't use.")
}

async function connectWebBle(): Promise<Transport> {
  const bt = (navigator as AnyDevice).bluetooth
  const device = await bt.requestDevice({ acceptAllDevices: true, optionalServices: KNOWN_SERVICES })
  const server = await device.gatt.connect()
  const characteristic = await findWritableWeb(server)
  return {
    kind: "web-ble",
    name: device.name || "Bluetooth printer",
    ref: { id: device.id },
    async write(chunks) {
      const data = concat(chunks)
      for (let i = 0; i < data.length; i += BLE_CHUNK) {
        const piece = data.slice(i, i + BLE_CHUNK)
        if (characteristic.properties.writeWithoutResponse) await characteristic.writeValueWithoutResponse(piece)
        else await characteristic.writeValueWithResponse(piece)
        await sleep(BLE_GAP_MS)
      }
    },
    async close() {
      try {
        device.gatt.disconnect()
      } catch {
        // already gone
      }
    },
  }
}

// ---- Native (Android / iPhone app) Bluetooth LE ---------------------------

export function nativeBleSupported(): boolean {
  return Capacitor.isNativePlatform()
}

let bleReady = false

async function connectNativeBle(ref?: Transport["ref"]): Promise<Transport> {
  if (!bleReady) {
    await BleClient.initialize({ androidNeverForLocation: true })
    bleReady = true
  }
  let deviceId = ref?.id
  let name = "Bluetooth printer"
  if (!deviceId) {
    const device = await BleClient.requestDevice({ optionalServices: KNOWN_SERVICES })
    deviceId = device.deviceId
    name = device.name || name
  }
  await BleClient.connect(deviceId)
  const services = await BleClient.getServices(deviceId)
  let target: { service: string; characteristic: string; withoutResponse: boolean } | null = null
  for (const service of services) {
    for (const c of service.characteristics) {
      const withoutResponse = !!c.properties.writeWithoutResponse
      if (withoutResponse || c.properties.write) {
        const candidate = { service: service.uuid, characteristic: c.uuid, withoutResponse }
        if (KNOWN_SERVICES.includes(service.uuid.toLowerCase())) {
          target = candidate
          break
        }
        target = target || candidate
      }
    }
    if (target && KNOWN_SERVICES.includes(target.service.toLowerCase())) break
  }
  if (!target) {
    await BleClient.disconnect(deviceId).catch(() => {})
    throw new PrinterError(
      "This Bluetooth device doesn't accept print data",
      "It may be a classic-Bluetooth-only printer. iPhones can only use Low Energy (BLE) printers.",
    )
  }
  const { service, characteristic, withoutResponse } = target
  const id = deviceId
  return {
    kind: "native-ble",
    name,
    ref: { id },
    async write(chunks) {
      const data = concat(chunks)
      for (let i = 0; i < data.length; i += BLE_CHUNK) {
        const piece = numbersToDataView(Array.from(data.slice(i, i + BLE_CHUNK)))
        if (withoutResponse) await BleClient.writeWithoutResponse(id, service, characteristic, piece)
        else await BleClient.write(id, service, characteristic, piece)
        await sleep(BLE_GAP_MS)
      }
    },
    async close() {
      await BleClient.disconnect(id).catch(() => {})
    },
  }
}

// ---- entry points ----------------------------------------------------------

/** Which connection types this device can offer, best first. */
export function availableKinds(): PrinterKind[] {
  const kinds: PrinterKind[] = []
  if (nativeBleSupported()) kinds.push("native-ble")
  if (usbSupported()) kinds.push("usb")
  if (webBleSupported()) kinds.push("web-ble")
  return kinds
}

export function kindLabel(kind: PrinterKind): string {
  return kind === "usb" ? "USB cable" : "Bluetooth"
}

/** Opens the system picker (needs a tap) and connects. `ref` reconnects without asking. */
export async function connectPrinter(kind: PrinterKind, ref?: Transport["ref"]): Promise<Transport> {
  try {
    if (kind === "usb") return await connectUsb(ref)
    if (kind === "web-ble") return await connectWebBle()
    return await connectNativeBle(ref)
  } catch (err) {
    if (err instanceof PrinterError) throw err
    const message = err instanceof Error ? err.message : String(err)
    if (/cancel|chose|no device|not selected|aborted|NotFoundError/i.test(message)) {
      throw new PrinterError("No printer was chosen")
    }
    if (/permission|denied|NotAllowed|SecurityError/i.test(message)) {
      throw new PrinterError("Bluetooth or USB permission was denied", "Allow it in the browser or the phone's settings and try again.")
    }
    throw new PrinterError(message || "Could not connect to the printer")
  }
}
