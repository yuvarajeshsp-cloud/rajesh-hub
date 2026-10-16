const SUPABASE_URL = (import.meta.env.PUBLIC_SUPABASE_URL as string | undefined) || '';

// Photos are served through Netlify's image CDN, resized and converted to
// WebP/AVIF automatically (Supabase URLs are allowed in netlify.toml).
// Elsewhere (local preview) the original file is used.
export function sizedImage(src: string, width: number): string {
  if (!import.meta.env.PROD || !process.env.NETLIFY || src.endsWith('.svg')) return src;
  if (!src.startsWith('/') && !(SUPABASE_URL && src.startsWith(`${SUPABASE_URL}/storage/`))) return src;
  return `/.netlify/images?url=${encodeURIComponent(src)}&w=${width}`;
}

