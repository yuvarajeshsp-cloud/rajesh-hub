import { Preferences } from "@capacitor/preferences"

/**
 * Supabase's default session storage is plain browser localStorage. Inside
 * a Capacitor WebView that's held far less durably than it is in a real
 * browser tab — iOS in particular can evict WKWebView storage under disk
 * pressure or after the app sits unused for a while, which is what was
 * forcing a fresh email/password sign-in on every app open. Capacitor's
 * Preferences plugin persists to native storage (UserDefaults on iOS,
 * SharedPreferences on Android) instead, which survives exactly the
 * conditions that were wiping the session. On the web build, Preferences'
 * own web implementation just delegates to localStorage, so this is a safe
 * drop-in everywhere — not only inside the native app.
 */
export const capacitorSupabaseStorage = {
  async getItem(key: string): Promise<string | null> {
    const { value } = await Preferences.get({ key })
    return value
  },
  async setItem(key: string, value: string): Promise<void> {
    await Preferences.set({ key, value })
  },
  async removeItem(key: string): Promise<void> {
    await Preferences.remove({ key })
  },
}
