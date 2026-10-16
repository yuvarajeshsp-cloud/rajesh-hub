// Supabase Edge Function: starts a Twilio Verify SMS OTP to the caller's
// own phone number (never a client-supplied number — always the one
// already on their profile, so this can't be used to verify an arbitrary
// number). This is the primary onboarding-verification channel; the
// frontend falls back to email OTP (Supabase's own signInWithOtp, no edge
// function needed) whenever this fails to send — e.g. Twilio Verify isn't
// configured yet, the number is unreachable, or the account has hit
// Twilio's rate limit.

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
  const verifyRes = await fetch(
    `https://verify.twilio.com/v2/Services/${verifyServiceSid}/Verifications`,
    {
      method: "POST",
      headers: { Authorization: twilioAuth, "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ To: phone, Channel: "sms" }),
    },
  )
  const verifyJson = await verifyRes.json()
  if (!verifyRes.ok) {
    return jsonResponse({ success: false, error: verifyJson?.message || "Failed to send SMS code" }, 502)
  }

  return jsonResponse({ success: true, phone })
})
