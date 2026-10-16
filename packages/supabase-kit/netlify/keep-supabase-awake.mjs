// Supabase's free plan pauses a project after about a week with no activity,
// which takes the whole app (sign-in included) offline until someone restores
// it by hand. This runs every two days and makes one tiny database read so the
// project always counts as active. It reads the same public URL/anon key the
// web app already ships with; the query returns no private data.
export default async () => {
  const url = process.env.VITE_SUPABASE_URL
  const key = process.env.VITE_SUPABASE_ANON_KEY
  if (!url || !key) {
    console.error("keep-supabase-awake: VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY not set")
    return new Response("not configured", { status: 500 })
  }

  const res = await fetch(`${url}/rest/v1/platform_settings?select=id&limit=1`, {
    headers: { apikey: key, Authorization: `Bearer ${key}` },
  })
  console.log(`keep-supabase-awake: Supabase responded ${res.status}`)
  return new Response(`ok ${res.status}`, { status: res.ok ? 200 : 502 })
}

export const config = { schedule: "0 3 */2 * *" }
