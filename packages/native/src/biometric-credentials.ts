import { Capacitor } from "@capacitor/core"
import { SecureStoragePlugin } from "capacitor-secure-storage-plugin"

/**
 * The email/password used to sign back in with Face ID / Touch ID after a
 * full sign-out, stored in the OS Keychain (not the app's own preferences)
 * so it isn't sitting in plain app storage. Access to it is still gated by
 * our own `authenticateWithBiometry()` call before it's ever read — the
 * Keychain item itself isn't biometry-locked at the OS level, so treat that
 * check as a hard requirement at every call site, not optional.
 */
const EMAIL_KEY = "biometric_login_email"
const PASSWORD_KEY = "biometric_login_password"
const DISPLAY_NAME_KEY = "biometric_login_display_name"

export interface StoredCredentials {
  email: string
  password: string
  displayName: string | null
}

export async function saveBiometricCredentials(email: string, password: string, displayName?: string | null): Promise<void> {
  if (!Capacitor.isNativePlatform()) return
  await SecureStoragePlugin.set({ key: EMAIL_KEY, value: email })
  await SecureStoragePlugin.set({ key: PASSWORD_KEY, value: password })
  if (displayName) {
    await SecureStoragePlugin.set({ key: DISPLAY_NAME_KEY, value: displayName })
  } else {
    try {
      await SecureStoragePlugin.remove({ key: DISPLAY_NAME_KEY })
    } catch {
      // nothing stored
    }
  }
}

export async function getBiometricCredentials(): Promise<StoredCredentials | null> {
  if (!Capacitor.isNativePlatform()) return null
  try {
    const [{ value: email }, { value: password }] = await Promise.all([
      SecureStoragePlugin.get({ key: EMAIL_KEY }),
      SecureStoragePlugin.get({ key: PASSWORD_KEY }),
    ])
    let displayName: string | null = null
    try {
      displayName = (await SecureStoragePlugin.get({ key: DISPLAY_NAME_KEY })).value
    } catch {
      // saved before display names were tracked, or never set — fall back to email
    }
    return { email, password, displayName }
  } catch {
    return null
  }
}

export async function hasBiometricCredentials(): Promise<boolean> {
  return (await getBiometricCredentials()) !== null
}

export async function clearBiometricCredentials(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return
  for (const key of [EMAIL_KEY, PASSWORD_KEY, DISPLAY_NAME_KEY]) {
    try {
      await SecureStoragePlugin.remove({ key })
    } catch {
      // nothing stored
    }
  }
}
