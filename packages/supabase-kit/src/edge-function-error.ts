import { FunctionsHttpError } from "@supabase/supabase-js"

/**
 * supabase.functions.invoke() throws a generic FunctionsHttpError
 * ("Edge Function returned a non-2xx status code") for ANY non-2xx
 * response — it never surfaces the function's own JSON error body, even
 * though every edge function in this app returns { success: false, error }
 * with a specific, user-facing message. Read that body back out here
 * instead of showing the generic message.
 */
export async function edgeFunctionErrorMessage(error: unknown, fallback: string): Promise<string> {
  if (error instanceof FunctionsHttpError) {
    try {
      const body = await error.context.json()
      if (body?.error) return body.error
    } catch {
      // response body wasn't JSON — fall through to the generic message
    }
  }
  return error instanceof Error ? error.message : fallback
}
