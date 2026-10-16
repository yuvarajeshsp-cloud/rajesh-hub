export type InstagramPost = {
  id: string;
  caption?: string;
  media_type: 'IMAGE' | 'VIDEO' | 'CAROUSEL_ALBUM';
  media_url: string;
  thumbnail_url?: string;
  permalink: string;
};

let cache: Promise<InstagramPost[]> | undefined;

// Latest posts from the shop's Instagram professional account, fetched when
// the site is built (a daily Netlify build hook keeps it fresh — see
// docs/META_SETUP.md). Without a token the section is simply hidden.
export function getInstagramPosts(limit = 8): Promise<InstagramPost[]> {
  cache ??= load(limit);
  return cache;
}

async function load(limit: number): Promise<InstagramPost[]> {
  const token = import.meta.env.INSTAGRAM_ACCESS_TOKEN;
  if (!token) return [];
  try {
    const fields = 'id,caption,media_type,media_url,thumbnail_url,permalink';
    const res = await fetch(
      `https://graph.instagram.com/me/media?fields=${fields}&limit=${limit}&access_token=${encodeURIComponent(token)}`,
    );
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    const { data } = (await res.json()) as { data: InstagramPost[] };
    return data.filter((p) => p.media_url || p.thumbnail_url);
  } catch (err) {
    console.error('[instagram] Could not load feed:', err);
    return [];
  }
}
