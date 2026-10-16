// Meta Conversions API helper. Sends nothing unless both the Pixel ID and the
// access token are configured.
import { createHash } from 'node:crypto';

const GRAPH_VERSION = 'v23.0';

export const sha256 = (value) => createHash('sha256').update(value).digest('hex');

// Phone in E.164 digits (country code, no +), as Meta expects before hashing.
export function normalizePhone(raw) {
  const digits = String(raw || '').replace(/\D/g, '').replace(/^0+/, '');
  if (digits.length === 10) return `91${digits}`;
  return digits;
}

export function clientInfo(req, context) {
  return {
    client_ip_address: context?.ip || req.headers.get('x-nf-client-connection-ip') || undefined,
    client_user_agent: req.headers.get('user-agent') || undefined,
  };
}

export async function sendMetaEvent({ eventName, eventId, eventSourceUrl, userData, customData }) {
  const pixelId = process.env.PUBLIC_META_PIXEL_ID;
  const token = process.env.META_CAPI_TOKEN;
  if (!pixelId || !token) return { skipped: true };

  const payload = {
    data: [
      {
        event_name: eventName,
        event_time: Math.floor(Date.now() / 1000),
        event_id: eventId,
        action_source: 'website',
        event_source_url: eventSourceUrl,
        user_data: Object.fromEntries(Object.entries(userData).filter(([, v]) => v)),
        ...(customData && { custom_data: customData }),
      },
    ],
    ...(process.env.META_TEST_EVENT_CODE && { test_event_code: process.env.META_TEST_EVENT_CODE }),
  };

  const res = await fetch(`https://graph.facebook.com/${GRAPH_VERSION}/${pixelId}/events?access_token=${encodeURIComponent(token)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) console.error('[meta] CAPI error', res.status, await res.text());
  return { ok: res.ok };
}
