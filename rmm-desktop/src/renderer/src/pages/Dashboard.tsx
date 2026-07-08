import { useMemo, useState } from 'react'
import { Plus, Search, RefreshCw, Monitor, Activity, Radio } from 'lucide-react'
import { useAuth } from '../auth'
import { useMachines } from '../useMachines'
import { MachineList } from '../components/MachineList'
import { TopBar } from '../components/TopBar'
import { AddMachineDialog } from '../components/AddMachineDialog'
import { RemoteViewer } from '../components/RemoteViewer'
import { ActivityLog } from '../components/ActivityLog'
import type { Machine } from '../types'

type Tab = 'machines' | 'activity'

export function Dashboard() {
  const { session, signOut } = useAuth()
  const base = session!.base
  const token = session!.token

  const { machines, wsState, error, refresh } = useMachines(base, token)
  const [query, setQuery] = useState('')
  const [adding, setAdding] = useState(false)
  const [viewing, setViewing] = useState<Machine | null>(null)
  const [tab, setTab] = useState<Tab>('machines')

  const onlineCount = useMemo(() => machines.filter((m) => m.is_online).length, [machines])

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="flex w-60 flex-shrink-0 flex-col border-r border-line bg-sidebar">
        {/* Brand */}
        <div className="flex items-center gap-2.5 px-5 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-signal text-white">
            <Radio className="h-5 w-5" />
          </div>
          <div>
            <div className="text-sm font-semibold text-fg">RMM Console</div>
            <div className="text-xs text-dim">
              {onlineCount} / {machines.length} online
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-1 px-3 py-2">
          <div
            onClick={() => setTab('machines')}
            className={`nav-item ${tab === 'machines' ? 'nav-item-active' : ''}`}
          >
            <Monitor className="h-4 w-4" />
            Machines
          </div>
          <div
            onClick={() => setTab('activity')}
            className={`nav-item ${tab === 'activity' ? 'nav-item-active' : ''}`}
          >
            <Activity className="h-4 w-4" />
            Activity
          </div>
        </nav>

        <div className="mt-auto px-5 py-4">
          <div className="flex items-center gap-2 text-xs text-dim">
            <span
              className={`h-2 w-2 rounded-full ${
                wsState === 'open' ? 'dot-online' : 'dot-offline'
              }`}
            />
            {wsState === 'open' ? 'Live' : 'Reconnecting…'}
          </div>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          email={session!.user.email}
          online={onlineCount}
          total={machines.length}
          wsState={wsState}
          onSignOut={signOut}
        />

        <main className="flex-1 overflow-auto px-8 py-6">
          <div className="mx-auto max-w-5xl">
            {tab === 'machines' ? (
              <>
                <div className="mb-5">
                  <h1 className="text-xl font-semibold text-fg">Machines</h1>
                  <p className="text-sm text-dim">Monitor and connect to managed machines</p>
                </div>

                <div className="flex items-center gap-3">
                  <div className="relative flex-1">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
                    <input
                      className="field pl-9"
                      placeholder="Search by name, host, IP, or user"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </div>
                  <button className="btn-ghost" onClick={refresh} title="Refresh">
                    <RefreshCw className="h-4 w-4" />
                  </button>
                  <button className="btn-primary" onClick={() => setAdding(true)}>
                    <Plus className="h-4 w-4" />
                    Add machine
                  </button>
                </div>

                {error && (
                  <div className="mt-4 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
                    {error}
                  </div>
                )}

                <MachineList machines={machines} query={query} onOpen={setViewing} />
              </>
            ) : (
              <>
                <div className="mb-5">
                  <h1 className="text-xl font-semibold text-fg">Activity</h1>
                  <p className="text-sm text-dim">Session and connection history</p>
                </div>
                <ActivityLog base={base} token={token} machines={machines} />
              </>
            )}
          </div>
        </main>
      </div>

      {adding && (
        <AddMachineDialog
          base={base}
          token={token}
          serverUrl={base}
          onClose={() => setAdding(false)}
          onEnrolled={refresh}
        />
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