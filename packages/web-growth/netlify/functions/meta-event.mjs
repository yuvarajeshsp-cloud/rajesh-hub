// Server-side copy of browser events (Conversions API), so ad reporting still
// works when the Pixel is blocked. Only a fixed set of events is accepted.
import { clientInfo, sendMetaEvent } from '../lib/meta.mjs';

const ALLOWED = new Set(['Contact', 'ViewContent', 'AddToWishlist']);

export default async (req, context) => {
  if (req.method !== 'POST') return new Response(null, { status: 405 });
  let body;
  try {
    body = await req.json();
  } catch {
    return new Response(null, { status: 400 });
  }
  if (!ALLOWED.has(body.event_name) || typeof body.event_id !== 'string') return new Response(null, { status: 422 });

  const str = (v, n) => (typeof v === 'string' && v ? v.slice(0, n) : undefined);
  // Optional product details (design codes from /catalog.xml), checked strictly.
  const cd = body.custom_data && typeof body.custom_data === 'object' ? body.custom_data : null;
  const ids = Array.isArray(cd?.content_ids) ? cd.content_ids.filter((x) => typeof x === 'string' && /^[\w-]{1,40}$/.test(x)).slice(0, 20) : [];
  const customData = ids.length
    ? {
        content_ids: ids,
        content_type: 'product',
        ...(Number.isFinite(cd.value) && cd.value >= 0 && { value: cd.value, currency: 'INR' }),
      }
    : undefined;
  await sendMetaEvent({
    eventName: body.event_name,
    eventId: body.event_id.slice(0, 100),
    eventSourceUrl: str(body.event_source_url, 500),
    userData: { fbp: str(body.fbp, 200), fbc: str(body.fbc, 500), ...clientInfo(req, context) },
    customData,
  }).catch((err) => console.error('[meta-event]', err));

  return new Response(null, { status: 204 });
};
