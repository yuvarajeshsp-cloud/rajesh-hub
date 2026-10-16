import { createClient } from "@supabase/supabase-js"

type AuthStorage = {
  getItem(key: string): Promise<string | null> | string | null
  setItem(key: string, value: string): Promise<void> | void
  removeItem(key: string): Promise<void> | void
}

/**
 * One way to create the Supabase client in every hub app (from Embroidery-Shop-Manager).
 * On phones pass `storage: capacitorSupabaseStorage` from @rajesh-hub/native so the
 * session survives the WebView clearing localStorage.
 * Passkeys also need turning on in the Supabase dashboard
 * (Authentication > Sign In / Providers > Passkeys).
 */
export function createHubClient(url: string, anonKey: string, opts: { storage?: AuthStorage; passkeys?: boolean } = {}) {
  return createClient(url, anonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      ...(opts.storage ? { storage: opts.storage } : {}),
      ...(opts.passkeys !== false ? { experimental: { passkey: true } } : {}),
    },
  })
}
