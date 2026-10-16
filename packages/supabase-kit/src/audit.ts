import type { SupabaseClient } from "@supabase/supabase-js"

// Audit trail (from Embroidery-Shop-Manager). Writes one row per important change
// to an `audit_logs` table; failures are logged, never thrown, so auditing can't
// break the action itself. Table shape: see ../README.md.

export interface AuditUser {
  id: string
  display_name?: string | null
}

export function createAuditLogger(supabase: SupabaseClient, table = "audit_logs") {
  return async function logAudit(
    user: AuditUser | null,
    tableName: string,
    recordId: string,
    action: string,
    previousValues: Record<string, unknown> | null = null,
    newValues: Record<string, unknown> | null = null,
    reason: string | null = null,
  ) {
    try {
      await supabase.from(table).insert({
        user_id: user?.id ?? null,
        user_name: user?.display_name ?? "System",
        table_name: tableName,
        record_id: recordId,
        action,
        previous_values: previousValues,
        new_values: newValues,
        reason,
      })
    } catch (err) {
      console.error("Failed to write audit log:", err)
    }
  }
}
