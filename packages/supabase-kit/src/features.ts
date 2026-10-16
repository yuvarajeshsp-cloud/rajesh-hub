// Feature flags (pattern from Embroidery-Shop-Manager): modules that are built but
// held back from a release. Each app declares its own flags:
//
//   export const FEATURES = defineFeatures({ subscription: false, whatsapp: false })
//   if (FEATURES.whatsapp) { ... }
//
// If a module also has a database-side switch, flip both together.
export function defineFeatures<T extends Record<string, boolean>>(flags: T): Readonly<T> {
  return Object.freeze({ ...flags })
}
