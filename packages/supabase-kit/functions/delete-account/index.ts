// Supabase Edge Function: lets a signed-in user permanently delete their own
// account (required by Google Play and the App Store for apps with sign-up).
//
// Who can delete what is decided here, server-side, not by the client:
//  * Platform admins cannot delete themselves this way.
//  * The only Administrator of a shop that still has other members is
//    blocked — deleting them would leave a shop nobody can manage. They have
//    to promote someone else first (or remove the other members).
//  * Everyone else leaves; the shop and its records stay, with the person's
//    name and links scrubbed (see purge_account()).
//  * If they are the shop's only member, the whole shop and its data is
//    deleted — and the client must say so and ask for confirmation.
// The caller must send { confirm: "DELETE" }.

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  })
}

const ATTACHMENTS_BUCKET = "order-attachments"

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders })
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY")
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")
  if (!supabaseUrl || !anonKey || !serviceRoleKey) {
    return jsonResponse({ success: false, error: "Supabase environment not available" }, 500)
  }

  const callerToken = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "")
  if (!callerToken) {
    return jsonResponse({ success: false, error: "Missing Authorization header" }, 401)
  }
  const callerRes = await fetch(`${supabaseUrl}/auth/v1/user`, {
    headers: { Authorization: `Bearer ${callerToken}`, apikey: anonKey },
  })
  if (!callerRes.ok) {
    return jsonResponse({ success: false, error: "Invalid or expired session" }, 401)
  }
  const callerUser = await callerRes.json()

  let payload: { confirm?: string }
  try {
    payload = await req.json()
  } catch {
    return jsonResponse({ success: false, error: "Invalid JSON body" }, 400)
  }
  if (payload.confirm !== "DELETE") {
    return jsonResponse({ success: false, error: 'Type DELETE to confirm' }, 400)
  }

  const svc = { Authorization: `Bearer ${serviceRoleKey}`, apikey: serviceRoleKey }
  const json = { ...svc, "Content-Type": "application/json" }

  const adminRes = await fetch(`${supabaseUrl}/rest/v1/platform_admins?user_id=eq.${callerUser.id}&select=user_id`, { headers: svc })
  const adminRows = await adminRes.json()
  if (Array.isArray(adminRows) && adminRows.length > 0) {
    return jsonResponse({ success: false, error: "Platform admin accounts can't be deleted from the app" }, 403)
  }

  const profileRes = await fetch(
    `${supabaseUrl}/rest/v1/user_profiles?id=eq.${callerUser.id}&select=role,organization_id`,
    { headers: svc },
  )
  const profileRows = await profileRes.json()
  const profile = Array.isArray(profileRows) ? profileRows[0] : null

  // No profile left: an earlier attempt already purged the data but failed
  // before removing the sign-in. Finish the job so a retry can't get stuck.
  let storagePaths: string[] = []
  if (profile) {
    const membersRes = await fetch(
      `${supabaseUrl}/rest/v1/user_profiles?organization_id=eq.${profile.organization_id}&select=id,role,is_active`,
      { headers: svc },
    )
    const members: { id: string; role: string; is_active: boolean }[] = await membersRes.json()
    const others = members.filter((m) => m.id !== callerUser.id)
    const otherAdmins = others.filter((m) => m.role === "Administrator" && m.is_active)

    if (profile.role === "Administrator" && others.length > 0 && otherAdmins.length === 0) {
      return jsonResponse(
        {
          success: false,
          error:
            "You're the only Administrator and your shop still has other team members. Make someone else an Administrator (or remove the other members) before deleting your account.",
        },
        409,
      )
    }

    const deleteOrg = others.length === 0
    const purgeRes = await fetch(`${supabaseUrl}/rest/v1/rpc/purge_account`, {
      method: "POST",
      headers: json,
      body: JSON.stringify({ p_user: callerUser.id, p_delete_org: deleteOrg }),
    })
    if (!purgeRes.ok) {
      const errText = await purgeRes.text()
      return jsonResponse({ success: false, error: `Failed to delete account data: ${errText}` }, 500)
    }
    storagePaths = (await purgeRes.json()) || []
  }

  if (storagePaths.length > 0) {
    await fetch(`${supabaseUrl}/storage/v1/object/${ATTACHMENTS_BUCKET}`, {
      method: "DELETE",
      headers: json,
      body: JSON.stringify({ prefixes: storagePaths }),
    })
  }

  const deleteRes = await fetch(`${supabaseUrl}/auth/v1/admin/users/${callerUser.id}`, {
    method: "DELETE",
    headers: svc,
  })
  if (!deleteRes.ok) {
    const errText = await deleteRes.text()
    return jsonResponse({ success: false, error: `Data deleted but sign-in removal failed: ${errText}` }, 502)
  }

  return jsonResponse({ success: true })
})
