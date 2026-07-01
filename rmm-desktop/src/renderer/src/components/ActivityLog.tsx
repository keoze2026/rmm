import { useCallback, useEffect, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { listActivity } from '../api'
import type { ActivityEntry, Machine } from '../types'
import { relativeTime } from './StatusDot'

interface Props {
  base: string
  token: string
  machines: Machine[]
}

// Friendly labels + a dot color per event family.
const LABEL: Record<string, string> = {
  'admin.registered': 'Admin registered',
  'admin.login': 'Admin signed in',
  'agent.connected': 'Agent connected',
  'agent.disconnected': 'Agent disconnected',
  'machine.enrolled': 'Machine enrolled',
  'machine.deleted': 'Machine removed',
  'machine.token_regenerated': 'Token regenerated',
  'session.start': 'Session started',
  'session.end': 'Session ended'
}

function eventColor(event: string): string {
  if (event.startsWith('session.')) return 'text-signal'
  if (event === 'agent.connected') return 'text-online'
  if (event === 'agent.disconnected') return 'text-faint'
  if (event.startsWith('machine.')) return 'text-fg'
  return 'text-dim'
}

function label(event: string): string {
  return LABEL[event] ?? event
}

export function ActivityLog({ base, token, machines }: Props) {
  const [rows, setRows] = useState<ActivityEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const nameById = useMemo(() => {
    const map = new Map<string, string>()
    machines.forEach((m) => map.set(m.id, m.name))
    return map
  }, [machines])

  const load = useCallback(() => {
    listActivity(base, token, { limit: 200 })
      .then((r) => {
        setRows(r)
        setError(null)
      })
      .catch((e) => setError(e?.message ?? 'Failed to load activity'))
      .finally(() => setLoading(false))
  }, [base, token])

  useEffect(() => {
    load()
    const t = setInterval(load, 10000) // refresh every 10s
    return () => clearInterval(t)
  }, [load])

  return (
    <div className="mt-6">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-fg">Activity</h2>
        <button className="btn-ghost" onClick={load} title="Refresh">
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {error && (
        <div className="mb-3 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">
          {error}
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-line text-xs uppercase tracking-wide text-faint">
              <th className="px-4 py-3 font-medium">Event</th>
              <th className="px-4 py-3 font-medium">Machine</th>
              <th className="px-4 py-3 font-medium">Actor</th>
              <th className="px-4 py-3 font-medium text-right">When</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-line/50 last:border-0">
                <td className={`px-4 py-2.5 font-medium ${eventColor(r.event)}`}>
                  {label(r.event)}
                </td>
                <td className="px-4 py-2.5 text-dim">
                  {r.machine_id ? nameById.get(r.machine_id) ?? '—' : '—'}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-dim">{r.actor ?? '—'}</td>
                <td
                  className="px-4 py-2.5 text-right text-xs text-faint"
                  title={new Date(r.created_at).toLocaleString()}
                >
                  {relativeTime(r.created_at)}
                </td>
              </tr>
            ))}
            {rows.length === 0 && !loading && (
              <tr>
                <td className="px-4 py-8 text-center text-sm text-faint" colSpan={4}>
                  No activity yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}