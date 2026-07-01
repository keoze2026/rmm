import { Apple, Monitor, MonitorSmartphone, Cpu } from 'lucide-react'
import type { Machine } from '../types'
import { StatusDot, relativeTime } from './StatusDot'

function OsIcon({ os }: { os: string | null }) {
  const cls = 'h-4 w-4 text-faint'
  if (!os) return <MonitorSmartphone className={cls} />
  const o = os.toLowerCase()
  if (o.includes('win')) return <Monitor className={cls} />
  if (o.includes('darwin') || o.includes('mac')) return <Apple className={cls} />
  return <Cpu className={cls} />
}

interface Props {
  machines: Machine[]
  query: string
  onOpen: (m: Machine) => void
}

export function MachineList({ machines, query, onOpen }: Props) {
  const q = query.trim().toLowerCase()
  const filtered = q
    ? machines.filter(
        (m) =>
          m.name.toLowerCase().includes(q) ||
          (m.hostname ?? '').toLowerCase().includes(q) ||
          (m.ip_address ?? '').toLowerCase().includes(q) ||
          (m.os_username ?? '').toLowerCase().includes(q)
      )
    : machines

  if (machines.length === 0) {
    return (
      <div className="card mt-6 flex flex-col items-center justify-center gap-2 py-16 text-center">
        <p className="text-fg">No machines enrolled yet</p>
        <p className="text-sm text-dim">
          Add a machine to generate its agent token, then install the agent on the endpoint.
        </p>
      </div>
    )
  }

  if (filtered.length === 0) {
    return (
      <div className="card mt-6 py-12 text-center text-sm text-dim">
        No machines match “{query}”.
      </div>
    )
  }

  return (
    <div className="card mt-6 overflow-hidden">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-line text-xs uppercase tracking-wide text-faint">
            <th className="px-4 py-3 font-medium">Machine</th>
            <th className="px-4 py-3 font-medium">Host</th>
            <th className="px-4 py-3 font-medium">User</th>
            <th className="px-4 py-3 font-medium">IP</th>
            <th className="px-4 py-3 font-medium">Last seen</th>
            <th className="px-4 py-3 font-medium text-right">Agent</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((m) => (
            <tr
              key={m.id}
              onClick={() => onOpen(m)}
              className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-raised/60"
            >
              <td className="px-4 py-3">
                <div className="flex items-center gap-3">
                  <StatusDot online={m.is_online} />
                  <span className="font-medium text-fg">{m.name}</span>
                </div>
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2 font-mono text-xs text-dim">
                  <OsIcon os={m.os_name} />
                  {m.hostname ?? '—'}
                </div>
              </td>
              <td className="px-4 py-3 text-dim">{m.os_username ?? '—'}</td>
              <td className="px-4 py-3 font-mono text-xs text-dim">{m.ip_address ?? '—'}</td>
              <td className="px-4 py-3 text-dim">
                {m.is_online ? (
                  <span className="text-online">online</span>
                ) : (
                  relativeTime(m.last_seen_at)
                )}
              </td>
              <td className="px-4 py-3 text-right font-mono text-xs text-faint">
                {m.agent_version ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
