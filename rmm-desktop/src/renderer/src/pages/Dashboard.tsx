import { useMemo, useState } from 'react'
import { Plus, Search, RefreshCw } from 'lucide-react'
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
    <div className="flex h-full flex-col">
      <TopBar
        email={session!.user.email}
        online={onlineCount}
        total={machines.length}
        wsState={wsState}
        onSignOut={signOut}
      />

      <main className="flex-1 overflow-auto px-6 py-5">
        <div className="mx-auto max-w-5xl">
          {/* Tabs */}
          <div className="mb-5 flex items-center gap-1 border-b border-line">
            <button
              onClick={() => setTab('machines')}
              className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
                tab === 'machines'
                  ? 'border-signal text-fg'
                  : 'border-transparent text-dim hover:text-fg'
              }`}
            >
              Machines
            </button>
            <button
              onClick={() => setTab('activity')}
              className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
                tab === 'activity'
                  ? 'border-signal text-fg'
                  : 'border-transparent text-dim hover:text-fg'
              }`}
            >
              Activity
            </button>
          </div>

          {tab === 'machines' ? (
            <>
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
                <div className="mt-4 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">
                  {error}
                </div>
              )}

              <MachineList machines={machines} query={query} onOpen={setViewing} />
            </>
          ) : (
            <ActivityLog base={base} token={token} machines={machines} />
          )}
        </div>
      </main>

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