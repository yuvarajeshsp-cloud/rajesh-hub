import { Preferences } from "@capacitor/preferences"
import { Capacitor } from "@capacitor/core"
import { BiometricAuth, type CheckBiometryResult } from "@aparajita/capacitor-biometric-auth"

/**
 * Whether the signed-in user has opted into unlocking the app with device
 * biometrics (Face ID / Touch ID / Android fingerprint) instead of typing
 * their password again. This is a per-device preference, not an account
 * setting — it only controls whether the already-persisted Supabase
 * session is gated behind a biometric prompt on this specific device.
 */
const ENABLED_KEY = "biometric_unlock_enabled"

export async function isBiometricUnlockEnabled(): Promise<boolean> {
  if (!Capacitor.isNativePlatform()) return false
  const { value } = await Preferences.get({ key: ENABLED_KEY })
  return value === "true"
}

export async function setBiometricUnlockEnabled(enabled: boolean): Promise<void> {
  await Preferences.set({ key: ENABLED_KEY, value: enabled ? "true" : "false" })
}

export async function getBiometryAvailability(): Promise<CheckBiometryResult | null> {
  if (!Capacitor.isNativePlatform()) return null
  try {
    return await BiometricAuth.checkBiometry()
  } catch {
    return null
  }
}

// The system Face ID / Touch ID sheet itself triggers an iOS app
// resign-active/become-active transition as it opens and closes (confirmed
// on-device: `appStateChange` fires isActive:false the instant the prompt is
// requested). Without accounting for this, the become-active event that
// follows when the prompt dismisses re-fires the app's lock check and
// re-locks the screen immediately after a successful unlock — the "keeps
// logging out and back in" loop.
//
// `authInFlight` covers the prompt itself: while true, the become-active
// event that can race with the authenticate() promise resolving is ignored.
// `suppressNextResume` covers what happens right after: rather than guessing
// how long the dismiss animation takes with a timeout, it's set once the
// prompt settles and consumed by exactly the next isActive:true event,
// however long that actually takes to arrive. A later, unrelated
// backgrounding clears any never-consumed suppression so it can't linger
// and swallow a real future lock check.
let authInFlight = false
let suppressNextResume = false

export function isBiometricAuthInFlight(): boolean {
  return authInFlight
}

/** Call from the appStateChange listener when isActive is true. Returns true if this resume should be ignored. */
export function consumeBiometricResumeSuppression(): boolean {
  if (suppressNextResume) {
    suppressNextResume = false
    return true
  }
  return false
}

/**
 * Non-consuming check for an initial lock check that runs *before* the
 * appStateChange listener even exists yet — e.g. right after signing in
 * with the "Sign in with Face ID" button, where the sign-in's own prompt
 * causes a resign/become-active pair that hasn't been delivered yet at the
 * moment this runs. Skip that one check here, but leave the flag itself for
 * the listener to actually consume once it's registered and the real event
 * eventually arrives (it's still on its way, just delayed by the OS's
 * dismiss animation) — consuming it here too would mean nothing is left to
 * suppress that later, real event, re-locking anyway a moment after.
 */
export function isBiometricResumeSuppressionPending(): boolean {
  return suppressNextResume
}

/** Call from the appStateChange listener when isActive is false, outside of an in-flight prompt. */
export function clearStaleBiometricResumeSuppression(): void {
  suppressNextResume = false
}

/** Prompts for biometric verification. Resolves true on success, false on any failure or cancel. */
export async function authenticateWithBiometry(reason: string): Promise<boolean> {
  authInFlight = true
  try {
    await BiometricAuth.authenticate({ reason, allowDeviceCredential: true, cancelTitle: "Use Password" })
    return true
  } catch {
    return false
  } finally {
    authInFlight = false
    suppressNextResume = true
  }
}
