import { useEffect, useState } from 'react'
import { Monitor } from 'lucide-react'
import { listActivity, listSessions } from '../../api'
import type { ActivityEntry, Machine, SessionEntry } from '../../types'

/** Shown for the rail icons the endpoint agent has no command for. */
export function Unavailable({ title, note }: { title: string; note: string }) {
  return (
    <div className="px-8 py-10">
      <div className="rounded border border-line bg-ink px-6 py-8 text-center">
        <div className="text-[15px] font-medium text-fg">{title}</div>
        <p className="mx-auto mt-2 max-w-sm text-[13px] leading-relaxed text-dim">{note}</p>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="flex border-b border-line py-2.5 text-[13px]">
      <div className="w-[150px] flex-shrink-0 text-dim">{label}</div>
      <div className="min-w-0 flex-1 break-words text-fg">{value ?? '—'}</div>
    </div>
  )
}

function NoGuest({ what }: { what: string }) {
  return (
    <div className="px-8 py-10 text-center text-[13px] text-dim">
      {what} becomes available once your guest has joined the session.
    </div>
  )
}

/** System info reported by the agent in its `hello` inventory. */
export function InfoPanel({ machine }: { machine: Machine | null }) {
  if (!machine) return <NoGuest what="System information" />
  return (
    <div className="px-8 py-6">
      <Row label="Name" value={machine.name} />
      <Row label="Hostname" value={machine.hostname} />
      <Row label="Operating system" value={machine.os_name} />
      <Row label="OS version" value={machine.os_version} />
      <Row label="Logged-in user" value={machine.os_username} />
      <Row label="IP address" value={machine.ip_address} />
      <Row label="CPU" value={machine.cpu_model} />
      <Row label="CPU cores" value={machine.cpu_cores} />
      <Row
        label="Memory"
        value={machine.ram_total_mb ? `${(machine.ram_total_mb / 1024).toFixed(1)} GB` : null}
      />
      <Row label="Agent version" value={machine.agent_version} />
      <Row label="Status" value={machine.is_online ? 'Online' : 'Offline'} />
      <Row
        label="Last seen"
        value={machine.last_seen_at ? new Date(machine.last_seen_at).toLocaleString() : null}
      />
    </div>
  )
}

/** Past remote sessions against this machine. */
export function HistoryPanel({
  base,
  token,
  machine
}: {
  base: string
  token: string
  machine: Machine | null
}) {
  const [rows, setRows] = useState<SessionEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!machine) return
    let alive = true
    listSessions(base, token, { machineId: machine.id, limit: 100 })
      .then((r) => alive && setRows(r))
      .catch(() => alive && setRows([]))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [base, token, machine])

  if (!machine) return <NoGuest what="Session history" />
  if (loading) return <div className="px-8 py-10 text-center text-[13px] text-dim">Loading…</div>
  if (!rows.length)
    return <div className="px-8 py-10 text-center text-[13px] text-dim">No sessions recorded yet.</div>

  return (
    <div className="px-8 py-6">
      {rows.map((s) => (
        <div key={s.id} className="flex items-center justify-between border-b border-line py-2.5 text-[13px]">
          <div>
            <div className="text-fg">{new Date(s.started_at).toLocaleString()}</div>
            <div className="text-[12px] text-dim">
              {s.kind}
              {s.user_notified ? ' · user notified' : ''}
            </div>
          </div>
          <div className="text-right">
            <div className={s.status === 'active' ? 'text-online' : 'text-dim'}>{s.status}</div>
            {s.duration_seconds != null && (
              <div className="text-[12px] text-dim">
                {Math.floor(s.duration_seconds / 60)}m {s.duration_seconds % 60}s
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

/** The server-side audit trail for this machine. */
export function LogsPanel({
  base,
  token,
  machine
}: {
  base: string
  token: string
  machine: Machine | null
}) {
  const [rows, setRows] = useState<ActivityEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!machine) return
    let alive = true
    listActivity(base, token, { machineId: machine.id, limit: 200 })
      .then((r) => alive && setRows(r))
      .catch(() => alive && setRows([]))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [base, token, machine])

  if (!machine) return <NoGuest what="The activity log" />
  if (loading) return <div className="px-8 py-10 text-center text-[13px] text-dim">Loading…</div>
  if (!rows.length)
    return <div className="px-8 py-10 text-center text-[13px] text-dim">Nothing logged yet.</div>

  return (
    <div className="px-8 py-6">
      {rows.map((a) => (
        <div key={a.id} className="flex gap-3 border-b border-line py-2 text-[13px]">
          <div className="w-[140px] flex-shrink-0 text-dim">
            {new Date(a.created_at).toLocaleString()}
          </div>
          <div className="min-w-0 flex-1">
            <span className="text-fg">{a.event}</span>
            {a.actor && <span className="text-dim"> · {a.actor}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}

/**
 * Terminal, files and download all run inside an active remote session — the
 * same session that notifies the person at the other end. This launches it.
 */
export function RemoteToolPanel({
  title,
  note,
  canOpen,
  onOpen
}: {
  title: string
  note: string
  canOpen: boolean
  onOpen: () => void
}) {
  return (
    <div className="px-8 py-10 text-center">
      <div className="text-[15px] font-medium text-fg">{title}</div>
      <p className="mx-auto mt-2 max-w-sm text-[13px] leading-relaxed text-dim">{note}</p>
      <button
        onClick={onOpen}
        disabled={!canOpen}
        className="mx-auto mt-5 flex items-center gap-2 rounded bg-signal px-6 py-2.5 text-[14px] font-medium text-white hover:bg-signalHover disabled:opacity-40"
      >
        <Monitor className="h-4 w-4" />
        Open remote session
      </button>
      {!canOpen && (
        <div className="mt-3 text-[12px] text-dim">Waiting for your guest to join…</div>
      )}
    </div>
  )
}
