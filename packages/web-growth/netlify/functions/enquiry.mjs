// Reports a website enquiry to Meta as a "Lead" (Conversions API). The
// enquiry itself is saved by Netlify Forms; the browser only calls this when
// the visitor accepted cookies, with the same event_id as the Pixel event so
// Meta counts it once.
import { clientInfo, normalizePhone, sendMetaEvent, sha256 } from '../lib/meta.mjs';

const clip = (v, n) => {
  const s = typeof v === 'string' ? v.trim() : '';
  return s ? s.slice(0, n) : null;
};

export default async (req, context) => {
  if (req.method !== 'POST') return new Response(null, { status: 405 });

  let body;
  try {
    body = await req.json();
  } catch {
    return new Response(null, { status: 400 });
  }

  const name = clip(body.name, 80);
  const phone = normalizePhone(body.phone);
  const eventId = clip(body.event_id, 100);
  if (!name || !eventId || phone.length < 10 || phone.length > 15) return new Response(null, { status: 422 });

  try {
    await sendMetaEvent({
      eventName: 'Lead',
      eventId,
      eventSourceUrl: clip(body.event_source_url, 500) || undefined,
      userData: {
        ph: [sha256(phone)],
        fn: [sha256(name.split(/\s+/)[0].toLowerCase())],
        country: [sha256('in')],
        fbp: clip(body.fbp, 200),
        fbc: clip(body.fbc, 500),
        ...clientInfo(req, context),
      },
      customData: { content_name: clip(body.service, 120) || 'enquiry' },
    });
  } catch (err) {
    console.error('[enquiry] Meta event failed', err);
  }

  return new Response(null, { status: 204 });
};
