// Environment variables read by the growth kit. In an Astro site these come from .env.
interface ImportMetaEnv {
  readonly PROD: boolean
  readonly PUBLIC_SITE_KEY?: string
  readonly PUBLIC_META_PIXEL_ID?: string
  readonly PUBLIC_SUPABASE_URL?: string
  readonly PUBLIC_SUPABASE_ANON_KEY?: string
  readonly PUBLIC_SHOP_ORG_SLUG?: string
  readonly INSTAGRAM_ACCESS_TOKEN?: string
}
interface ImportMeta {
  readonly env: ImportMetaEnv
}
declare const process: { env: Record<string, string | undefined> }
