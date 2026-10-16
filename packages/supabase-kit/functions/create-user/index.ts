// Supabase Edge Function: creates a new team member directly with a
// password, skipping the email-invite flow entirely — the account is
// immediately usable with the credentials the Administrator set.
//
// Creating an auth user with the service role key must never happen in the
// browser bundle, so this runs server-side only. The caller's own JWT is
// verified and their user_profiles.role checked before anything is
// created: only an Administrator may create users this way.

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
}

const VALID_ROLES = ["Administrator", "Manager", "Operator", "Accounts"]

interface CreateUserRequest {
  email: string
  display_name: string
  role: string
  password: string
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  })
}

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

  const authHeader = req.headers.get("Authorization") || ""
  const callerToken = authHeader.replace(/^Bearer\s+/i, "")
  if (!callerToken) {
    return jsonResponse({ success: false, error: "Missing Authorization header" }, 401)
  }

  // Verify the caller's identity with their own token (not the service key).
  const callerRes = await fetch(`${supabaseUrl}/auth/v1/user`, {
    headers: { Authorization: `Bearer ${callerToken}`, apikey: anonKey },
  })
  if (!callerRes.ok) {
    return jsonResponse({ success: false, error: "Invalid or expired session" }, 401)
  }
  const callerUser = await callerRes.json()

  // Confirm the caller is an Administrator by reading their profile with the
  // service key (bypasses RLS so we get the authoritative row).
  const profileRes = await fetch(
    `${supabaseUrl}/rest/v1/user_profiles?id=eq.${callerUser.id}&select=role,is_active,organization_id`,
    {
      headers: { Authorization: `Bearer ${serviceRoleKey}`, apikey: serviceRoleKey },
    },
  )
  const profileRows = await profileRes.json()
  const callerProfile = Array.isArray(profileRows) ? profileRows[0] : null
  if (!callerProfile || callerProfile.role !== "Administrator" || !callerProfile.is_active) {
    return jsonResponse({ success: false, error: "Only an active Administrator can create users" }, 403)
  }

  let payload: CreateUserRequest
  try {
    payload = await req.json()
  } catch {
    return jsonResponse({ success: false, error: "Invalid JSON body" }, 400)
  }

  const email = (payload.email || "").trim().toLowerCase()
  const displayName = (payload.display_name || "").trim()
  const role = payload.role
  const password = payload.password || ""

  if (!email || !displayName) {
    return jsonResponse({ success: false, error: "Name and email are required" }, 400)
  }
  if (!VALID_ROLES.includes(role)) {
    return jsonResponse({ success: false, error: "Invalid role" }, 400)
  }
  if (password.length < 6) {
    return jsonResponse({ success: false, error: "Password must be at least 6 characters" }, 400)
  }

  const createRes = await fetch(`${supabaseUrl}/auth/v1/admin/users`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${serviceRoleKey}`,
      apikey: serviceRoleKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      password,
      email_confirm: true,
      user_metadata: { display_name: displayName },
    }),
  })

  const createJson = await createRes.json()
  if (!createRes.ok) {
    const message = createJson?.msg || createJson?.error_description || createJson?.message || "Failed to create user"
    return jsonResponse({ success: false, error: message }, createRes.status === 422 ? 409 : 502)
  }

  const newUserId = createJson.id
  const profileInsertRes = await fetch(`${supabaseUrl}/rest/v1/user_profiles`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${serviceRoleKey}`,
      apikey: serviceRoleKey,
      "Content-Type": "application/json",
      Prefer: "return=minimal",
    },
    body: JSON.stringify({
      id: newUserId,
      display_name: displayName,
      email,
      role,
      is_active: true,
      // Created directly by a trusted Administrator, not the public
      // sign-up form — exempt from the sign-up phone verification gate.
      phone_verified: true,
      organization_id: callerProfile.organization_id,
    }),
  })

  if (!profileInsertRes.ok) {
    const errText = await profileInsertRes.text()
    return jsonResponse({ success: false, error: `User created but profile setup failed: ${errText}` }, 500)
  }

  return jsonResponse({ success: true, user_id: newUserId })
})
