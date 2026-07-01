import type { ActivityEntry, Machine, MachineEnrolled, SessionEntry, User } from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Normalise a server base URL (strip trailing slash). */
export function normalizeBase(url: string): string {
  return url.trim().replace(/\/+$/, '')
}

/** Build the admin WebSocket URL from the HTTP base + JWT. */
export function adminWsUrl(httpBase: string, token: string): string {
  const base = normalizeBase(httpBase)
  const ws = base.replace(/^http/i, (m) => (m.toLowerCase() === 'https' ? 'wss' : 'ws'))
  return `${ws}/ws/admin?token=${encodeURIComponent(token)}`
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') return body.detail
    return JSON.stringify(body)
  } catch {
    return res.statusText || `HTTP ${res.status}`
  }
}

export async function login(base: string, email: string, password: string): Promise<string> {
  const body = new URLSearchParams({ username: email, password })
  const res = await fetch(`${normalizeBase(base)}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body
  })
  if (!res.ok) throw new ApiError(res.status, await readError(res))
  const data = await res.json()
  return data.access_token as string
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` }
}

export async function getMe(base: string, token: string): Promise<User> {
  const res = await fetch(`${normalizeBase(base)}/api/auth/me`, { headers: authHeaders(token) })
  if (!res.ok) throw new ApiError(res.status, await readError(res))
  return res.json()
}

export async function listMachines(base: string, token: string): Promise<Machine[]> {
  const res = await fetch(`${normalizeBase(base)}/api/machines`, { headers: authHeaders(token) })
  if (!res.ok) throw new ApiError(res.status, await readError(res))
  return res.json()
}

export async function enrollMachine(
  base: string,
  token: string,
  name: string,
  notes?: string
): Promise<MachineEnrolled> {
  const res = await fetch(`${normalizeBase(base)}/api/machines`, {
    method: 'POST',
    headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, notes: notes || null })
  })
  if (!res.ok) throw new ApiError(res.status, await readError(res))
  return res.json()
}

export async function listActivity(
  base: string,
  token: string,
  opts: { machineId?: string; limit?: number } = {}
): Promise<ActivityEntry[]> {
  const q = new URLSearchParams()
  if (opts.machineId) q.set('machine_id', opts.machineId)
  q.set('limit', String(opts.limit ?? 200))
  const res = await fetch(`${normalizeBase(base)}/api/activity?${q.toString()}`, {
    headers: authHeaders(token)
  })
  if (!res.ok) throw new ApiError(res.status, await readError(res))
  return res.json()
}

export async function listSessions(
  base: string,
  token: string,
  opts: { machineId?: string; limit?: number } = {}
): Promise<SessionEntry[]> {
  const q = new URLSearchParams()
  if (opts.machineId) q.set('machine_id', opts.machineId)
  q.set('limit', String(opts.limit ?? 200))
  const res = await fetch(`${normalizeBase(base)}/api/sessions?${q.toString()}`, {
    headers: authHeaders(token)
  })
  if (!res.ok) throw new ApiError(res.status, await readError(res))
  return res.json()
}