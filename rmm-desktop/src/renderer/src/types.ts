// Mirrors the server's MachineOut / WS snapshot shapes.

export interface User {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  is_superadmin: boolean
}

// Full machine record from REST GET /api/machines.
export interface Machine {
  id: string
  name: string
  hostname: string | null
  os_name: string | null
  os_version: string | null
  os_username: string | null
  ip_address: string | null
  cpu_model: string | null
  cpu_cores: number | null
  ram_total_mb: number | null
  agent_version: string | null
  notes: string | null
  is_enabled: boolean
  is_online: boolean
  last_seen_at: string | null
}

// Returned once on enroll / token regenerate.
export interface MachineEnrolled extends Machine {
  agent_token: string
}

// Compact rows from the WS machines_snapshot.
export interface MachineSnapshotRow {
  id: string
  name: string
  is_online: boolean
  os_name: string | null
  hostname: string | null
  ip_address: string | null
  last_seen_at: string | null
}

export type WsInbound =
  | { type: 'machines_snapshot'; machines: MachineSnapshotRow[] }
  | { type: 'machine_status'; machine_id: string; online: boolean }
  | { type: 'machine_inventory'; machine_id: string; inventory: Record<string, unknown> }
  | { type: 'command_failed'; machine_id: string; reason: string }
  | { type: string; [k: string]: unknown }

export type WsState = 'connecting' | 'open' | 'closed'

export interface ActivityEntry {
  id: string
  event: string
  actor: string | null
  machine_id: string | null
  admin_id: string | null
  detail: Record<string, unknown> | null
  created_at: string
}

export interface SessionEntry {
  id: string
  machine_id: string
  admin_id: string | null
  kind: string
  status: string
  user_notified: boolean
  started_at: string
  ended_at: string | null
  duration_seconds: number | null
}