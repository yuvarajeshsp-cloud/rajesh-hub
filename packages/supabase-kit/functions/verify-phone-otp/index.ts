// Supabase Edge Function: checks a Twilio Verify SMS code against the
// caller's own phone number and, on success, marks onboarding complete.
//
// Unlike the email OTP path (which proves itself through Supabase Auth's
// own JWT amr claim — see mark_self_email_verified()), this check happens
// entirely against Twilio's API from here, so THIS function is the trusted
// verifier: on an "approved" result it writes phone_verified directly with
// the service role key, the same way create-user/invite-user already write
// profiles server-side.

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

interface VerifyRequest {
  code: string
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders })
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY")
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")
  const accountSid = Deno.env.get("TWILIO_ACCOUNT_SID")
  const authToken = Deno.env.get("TWILIO_AUTH_TOKEN")
  const verifyServiceSid = Deno.env.get("TWILIO_VERIFY_SERVICE_SID")
  if (!supabaseUrl || !anonKey || !serviceRoleKey || !accountSid || !authToken || !verifyServiceSid) {
    return jsonResponse({ success: false, error: "Phone verification is not configured" }, 500)
  }

  const authHeader = req.headers.get("Authorization") || ""
  const callerToken = authHeader.replace(/^Bearer\s+/i, "")
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

  let payload: VerifyRequest
  try {
    payload = await req.json()
  } catch {
    return jsonResponse({ success: false, error: "Invalid JSON body" }, 400)
  }
  const code = (payload.code || "").trim()
  if (!code) {
    return jsonResponse({ success: false, error: "Enter the code you received" }, 400)
  }

  const svc = { Authorization: `Bearer ${serviceRoleKey}`, apikey: serviceRoleKey }
  const profileRes = await fetch(
    `${supabaseUrl}/rest/v1/user_profiles?id=eq.${callerUser.id}&select=phone`,
    { headers: svc },
  )
  const profileRows = await profileRes.json()
  const phone = Array.isArray(profileRows) ? profileRows[0]?.phone : null
  if (!phone) {
    return jsonResponse({ success: false, error: "No phone number on file" }, 400)
  }

  const twilioAuth = "Basic " + btoa(`${accountSid}:${authToken}`)
  const checkRes = await fetch(
    `https://verify.twilio.com/v2/Services/${verifyServiceSid}/VerificationCheck`,
    {
      method: "POST",
      headers: { Authorization: twilioAuth, "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ To: phone, Code: code }),
    },
  )
  const checkJson = await checkRes.json()
  if (!checkRes.ok || checkJson.status !== "approved") {
    return jsonResponse({ success: false, error: "Incorrect or expired code" }, 400)
  }

  const updateRes = await fetch(`${supabaseUrl}/rest/v1/user_profiles?id=eq.${callerUser.id}`, {
    method: "PATCH",
    headers: { ...svc, "Content-Type": "application/json", Prefer: "return=minimal" },
    body: JSON.stringify({ phone_verified: true, updated_at: new Date().toISOString() }),
  })
  if (!updateRes.ok) {
    const errText = await updateRes.text()
    return jsonResponse({ success: false, error: `Verified but failed to complete setup: ${errText}` }, 500)
  }

  return jsonResponse({ success: true })
})
