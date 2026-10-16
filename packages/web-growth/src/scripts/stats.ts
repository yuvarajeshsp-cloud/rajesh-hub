// Anonymous item counters (from paavai-embroidery-web) for an Insights view and a
// "Most popular" sort: page views, ♡ taps and WhatsApp enquiries per item code.
// Needs the track_design_event(p_org_slug, p_code, p_kind) function in Supabase
// (see paavai-embroidery-web supabase/20261016000000_website_collections_stats.sql).
// Only the design code and the kind of action are sent — no cookies, no
// visitor ids — so this runs without the cookie consent. Each action is
// counted once per design per browser tab session.
const SUPABASE_URL = import.meta.env.PUBLIC_SUPABASE_URL as string;
const SUPABASE_KEY = import.meta.env.PUBLIC_SUPABASE_ANON_KEY as string;
const SHOP_ORG_SLUG = import.meta.env.PUBLIC_SHOP_ORG_SLUG as string;
const SITE_KEY = (import.meta.env.PUBLIC_SITE_KEY as string | undefined) || 'site';

type Kind = 'view' | 'shortlist' | 'enquire';

export function countDesign(code: string, kind: Kind) {
  const key = `${SITE_KEY}-stat:${kind}:${code.toUpperCase()}`;
  try {
    if (sessionStorage.getItem(key)) return;
    sessionStorage.setItem(key, '1');
  } catch {
    /* storage blocked: count anyway */
  }
  if (!SUPABASE_URL || !SUPABASE_KEY || !SHOP_ORG_SLUG) return;
  fetch(`${SUPABASE_URL}/rest/v1/rpc/track_design_event`, {
    method: 'POST',
    keepalive: true,
    headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ p_org_slug: SHOP_ORG_SLUG, p_code: code, p_kind: kind }),
  }).catch(() => {});
}

// WhatsApp links about designs: data-wa="design:PE-0001", or data-codes with
// a comma-separated list (shortlist and collection pages).
export function initStats() {
  document.addEventListener('click', (e) => {
    const a = (e.target as Element | null)?.closest<HTMLAnchorElement>('a[data-wa]');
    if (!a) return;
    const codes = a.dataset.codes
      ? a.dataset.codes.split(',')
      : a.dataset.wa?.startsWith('design:')
        ? [a.dataset.wa.slice(7)]
        : [];
    codes.filter(Boolean).forEach((c) => countDesign(c, 'enquire'));
  });
}
