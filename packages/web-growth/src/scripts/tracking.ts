// Consent, Meta Pixel, ad attribution and WhatsApp-click tracking.
//
// - Nothing is sent to Meta until the visitor accepts the consent banner.
// - Every event gets an event_id; the same id is sent from the browser (Pixel)
//   and the server (Conversions API) so Meta counts it once.
// - UTM tags / fbclid from Instagram links are remembered for 30 days and
//   attached to enquiries, so each one shows where the visitor came from.

declare global {
  interface Window {
    fbq?: ((...args: unknown[]) => void) & { callMethod?: unknown; queue?: unknown[]; loaded?: boolean; version?: string; push?: unknown };
    _fbq?: unknown;
  }
}

const PIXEL_ID = import.meta.env.PUBLIC_META_PIXEL_ID as string | undefined;
// Storage keys are prefixed per site (PUBLIC_SITE_KEY, e.g. "thulir") so two sites on one
// browser never share consent or attribution.
const SITE_KEY = (import.meta.env.PUBLIC_SITE_KEY as string | undefined) || 'site';
const CONSENT_KEY = `${SITE_KEY}-consent`;
const ATTR_KEY = `${SITE_KEY}-attribution`;
const ATTR_TTL_MS = 30 * 24 * 60 * 60 * 1000;

export type Attribution = {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  fbclid?: string;
  landing_page?: string;
  ts?: number;
};

const storage = {
  get(key: string): string | null {
    try { return localStorage.getItem(key); } catch { return null; }
  },
  set(key: string, value: string) {
    try { localStorage.setItem(key, value); } catch { /* private mode */ }
  },
};

// ---------- consent ----------

export const hasConsent = () => storage.get(CONSENT_KEY) === 'granted';
export const trackingEnabled = () => Boolean(PIXEL_ID) && hasConsent();

export function setConsent(granted: boolean) {
  storage.set(CONSENT_KEY, granted ? 'granted' : 'denied');
  if (granted) loadPixel();
}

export const consentAnswered = () => storage.get(CONSENT_KEY) !== null;
export const pixelConfigured = () => Boolean(PIXEL_ID);

// ---------- attribution ----------

export function captureAttribution() {
  const params = new URLSearchParams(location.search);
  const keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'fbclid'] as const;
  const found: Attribution = {};
  for (const k of keys) {
    const v = params.get(k);
    if (v) found[k] = v.slice(0, 200);
  }
  if (Object.keys(found).length > 0) {
    // Last non-empty touch wins: a new ad click replaces an older one.
    storage.set(ATTR_KEY, JSON.stringify({ ...found, landing_page: location.pathname, ts: Date.now() }));
  }
}

export function getAttribution(): Attribution {
  const raw = storage.get(ATTR_KEY);
  if (!raw) return {};
  try {
    const a = JSON.parse(raw) as Attribution;
    if (!a.ts || Date.now() - a.ts > ATTR_TTL_MS) return {};
    return a;
  } catch {
    return {};
  }
}

// Short human label that goes into the WhatsApp message, e.g.
// "via Instagram ad – bridal-diwali".
export function sourceLabel(): string {
  const a = getAttribution();
  const src = (a.utm_source || '').toLowerCase();
  const medium = (a.utm_medium || '').toLowerCase();
  if (!src && a.fbclid) return 'via Instagram/Facebook';
  if (!src) return 'via website';
  const name = src === 'ig' || src === 'instagram' ? 'Instagram' : src === 'fb' || src === 'facebook' ? 'Facebook' : a.utm_source;
  const kind = ['paid', 'cpc', 'ads', 'ad', 'paid_social'].includes(medium) ? ' ad' : medium === 'story' ? ' story' : medium === 'social' ? '' : medium ? ` ${medium}` : '';
  return `via ${name}${kind}${a.utm_campaign ? ` – ${a.utm_campaign}` : ''}`;
}

// ---------- Meta Pixel ----------

export function loadPixel() {
  if (!trackingEnabled() || window.fbq) return;
  /* Standard Meta Pixel bootstrap. */
  const n: any = (window.fbq = function (...args: unknown[]) {
    n.callMethod ? n.callMethod(...args) : n.queue.push(args);
  } as any);
  if (!window._fbq) window._fbq = n;
  n.push = n;
  n.loaded = true;
  n.version = '2.0';
  n.queue = [];
  const s = document.createElement('script');
  s.async = true;
  s.src = 'https://connect.facebook.net/en_US/fbevents.js';
  document.head.appendChild(s);
  n('init', PIXEL_ID);
  n('track', 'PageView');
}

export const newEventId = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

function readCookie(name: string): string | undefined {
  return document.cookie.split('; ').find((c) => c.startsWith(`${name}=`))?.split('=')[1];
}

// Meta's browser ids, sent to the server so Conversions API events match the
// same visitor. _fbc is built from fbclid if the Pixel hasn't set it yet.
export function metaBrowserIds(): { fbp?: string; fbc?: string } {
  if (!trackingEnabled()) return {};
  const fbp = readCookie('_fbp');
  let fbc = readCookie('_fbc');
  const { fbclid, ts } = getAttribution();
  if (!fbc && fbclid) fbc = `fb.1.${ts ?? Date.now()}.${fbclid}`;
  return { fbp, fbc };
}

// Browser-side event; returns the event_id to reuse server-side.
export function trackEvent(name: string, params: Record<string, unknown> = {}, eventId = newEventId()): string {
  if (trackingEnabled() && window.fbq) window.fbq('track', name, params, { eventID: eventId });
  return eventId;
}

// Product details for catalog events: content_ids are product codes, the same
// ids as in /catalog.xml, so Meta can match visits to catalog products.
export type ProductData = { content_ids: string[]; content_type: 'product'; value?: number; currency?: 'INR' };

// Mirror a browser event through the Conversions API (survives ad blockers).
export function sendServerEvent(name: 'Contact' | 'ViewContent' | 'AddToWishlist', eventId: string, product?: ProductData) {
  if (!trackingEnabled()) return;
  const body = JSON.stringify({
    event_name: name,
    event_id: eventId,
    event_source_url: location.href,
    ...(product && { custom_data: product }),
    ...metaBrowserIds(),
  });
  const url = '/.netlify/functions/meta-event';
  if (navigator.sendBeacon) navigator.sendBeacon(url, new Blob([body], { type: 'application/json' }));
  else fetch(url, { method: 'POST', body, headers: { 'Content-Type': 'application/json' }, keepalive: true }).catch(() => {});
}

// ---------- WhatsApp buttons ----------

// Any <a data-wa> gets the visitor's source appended to its pre-filled
// message, and the click is tracked as a "Contact".
export function wireWhatsAppLinks() {
  document.addEventListener('click', (e) => {
    const a = (e.target as Element | null)?.closest<HTMLAnchorElement>('a[data-wa]');
    if (!a) return;
    try {
      const url = new URL(a.href);
      const text = url.searchParams.get('text') ?? '';
      const tag = `(${sourceLabel()})`;
      if (!text.includes(tag)) url.searchParams.set('text', `${text}${text ? ' ' : ''}${tag}`.trim());
      a.href = url.toString();
    } catch { /* leave the link as is */ }
    const id = trackEvent('Contact', { content_name: a.dataset.wa || 'whatsapp' });
    sendServerEvent('Contact', id);
  });
}

export function initTracking() {
  captureAttribution();
  loadPixel();
  wireWhatsAppLinks();
}
