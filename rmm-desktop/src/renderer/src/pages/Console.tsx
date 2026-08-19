import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../auth'
import { getMachine } from '../api'
import { useMachines } from '../useMachines'
import { useSupportSessions } from '../useSupportSessions'
import { IconRail } from '../components/console/IconRail'
import { SectionPanel } from '../components/console/SectionPanel'
import { SessionList } from '../components/console/SessionList'
import { SessionDetail, type TabKey } from '../components/console/SessionDetail'
import { RemoteViewer } from '../components/RemoteViewer'
import type { Machine } from '../types'

/**
 * The whole console on one page: rail | section | session list | detail.
 * Selecting a session fills the detail column — nothing navigates away.
 */
export function Console() {
  const { session: auth, signOut } = useAuth()
  const base = auth!.base
  const token = auth!.token

  const { sessions, loading, error, create, end, rename } = useSupportSessions(base, token)
  const { machines, wsState } = useMachines(base, token)

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const [query, setQuery] = useState('')
  const [tab, setTab] = useState<TabKey>('session')
  const [creating, setCreating] = useState(false)
  const [editNonce, setEditNonce] = useState(0)
  const [viewing, setViewing] = useState<Machine | null>(null)
  const [joinError, setJoinError] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return sessions
    return sessions.filter(
      (s) => s.name.toLowerCase().includes(q) || s.code.toLowerCase().includes(q)
    )
  }, [sessions, query])

  // Keep a selection so the detail column is never empty for no reason.
  useEffect(() => {
    if (selectedId && sessions.some((s) => s.id === selectedId)) return
    setSelectedId(sessions.length ? sessions[0].id : null)
  }, [sessions, selectedId])

  const selected = sessions.find((s) => s.id === selectedId) ?? null
  const selectedMachine = selected?.machine_id
    ? machines.find((m) => m.id === selected.machine_id) ?? null
    : null

  const hostLabel = (auth!.user.full_name || auth!.user.email.split('@')[0] || 'host').toLowerCase()

  async function handleCreate() {
    setCreating(true)
    const row = await create()
    if (row) {
      setSelectedId(row.id)
      setTab('session')
    }
    setCreating(false)
  }

  async function handleJoin() {
    setJoinError(null)
    if (!selected) return
    if (!selected.machine_id) {
      setJoinError('No machine has joined this session yet.')
      return
    }
    // Prefer the live list; fall back to a direct fetch if it hasn't arrived.
    const known = machines.find((m) => m.id === selected.machine_id)
    if (known) {
      setViewing(known)
      return
    }
    try {
      setViewing(await getMachine(base, token, selected.machine_id))
    } catch {
      setJoinError('Could not load the joined machine.')
    }
  }

  function handleDelete() {
    const ids = checked.size ? Array.from(checked) : selected ? [selected.id] : []
    if (!ids.length) return
    ids.forEach((id) => void end(id))
    setChecked(new Set())
  }

  function toggleCheck(id: string) {
    setChecked((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleAll() {
    setChecked((prev) =>
      prev.size === filtered.length ? new Set() : new Set(filtered.map((s) => s.id))
    )
  }

  return (
    <div className="flex h-full bg-surface">
      <IconRail email={auth!.user.email} wsState={wsState} onSignOut={signOut} />

      <SectionPanel
        count={sessions.length}
        onCreate={handleCreate}
        creating={creating}
      />

      <SessionList
        sessions={filtered}
        selectedId={selectedId}
        checked={checked}
        query={query}
        hostLabel={hostLabel}
        loading={loading}
        onSelect={(id) => {
          setSelectedId(id)
          setJoinError(null)
        }}
        onToggleCheck={toggleCheck}
        onToggleAll={toggleAll}
        onQuery={setQuery}
        onJoin={handleJoin}
        onEdit={() => {
          setTab('session')
          setEditNonce((n) => n + 1)
        }}
        onDelete={handleDelete}
        onMore={() => setTab('info')}
      />

      <SessionDetail
        session={selected}
        machine={selectedMachine}
        base={base}
        token={token}
        tab={tab}
        onTab={setTab}
        editNonce={editNonce}
        onRename={rename}
        onJoin={handleJoin}
        joinError={joinError}
      />

      {error && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded bg-danger/10 px-4 py-2 text-[13px] text-danger">
          {error}
        </div>
      )}

      {viewing && (
        <RemoteViewer
          base={base}
          token={token}
          machine={viewing}
          onClose={() => setViewing(null)}
        />
      )}
    </div>
  )
}
