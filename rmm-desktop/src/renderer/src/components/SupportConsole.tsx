import { useEffect, useMemo, useState } from 'react'
import {
  Headphones, Plus, RefreshCw, Search, Trash2, Edit2, LogIn,
  MoreHorizontal, User, Copy, Check
} from 'lucide-react'

type Sess = {
  id: string
  code: string
  link: string
  name: string
  status: string      // waiting | joined | ended
  host?: string
  user?: string
}

export function SupportConsole({ base, token, email, onSignOut, wsState }:{
  base: string; token: string; email: string; onSignOut: () => void; wsState: string
}) {
  const api = base.trim().replace(/\/+$/, '')
  const [sessions, setSessions] = useState<Sess[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [invite, setInvite] = useState<'code' | 'link'>('code')
  const [copied, setCopied] = useState('')

  const sel = sessions.find((s) => s.id === selected) || null

  async function refresh() {
    try {
      const r = await fetch(`${api}/api/support/list`, { headers: { Authorization: `Bearer ${token}` } })
      if (!r.ok) return
      const rows = await r.json()
      setSessions((prev) =>
        rows.map((x: any) => {
          const old = prev.find((p) => p.id === x.id)
          return {
            id: x.id,
            code: x.code,
            link: old?.link || `${api}/join/${x.code}`,
            name: x.label || x.name || `Session ${x.code}`,
            status: x.status,
            host: x.host,
            user: x.user,
          }
        })
      )
    } catch {}
  }

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 4000)
    return () => clearInterval(t)
  }, [])

  async function create() {
    try {
      const r = await fetch(`${api}/api/support/create`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) return
      const d = await r.json()
      const s: Sess = { id: d.session_id, code: d.code, link: d.link, name: `Session ${d.code}`, status: d.status }
      setSessions((p) => [s, ...p])
      setSelected(s.id)
    } catch {}
  }

  async function endSession(id: string) {
    try {
      await fetch(`${api}/api/support/${id}/end`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } })
      setSessions((p) => p.filter((s) => s.id !== id))
      if (selected === id) setSelected(null)
    } catch {}
  }

  function copy(text: string, which: string) {
    navigator.clipboard.writeText(text)
    setCopied(which); setTimeout(() => setCopied(''), 1500)
  }

  const filtered = useMemo(
    () => sessions.filter((s) => s.name.toLowerCase().includes(query.toLowerCase()) || s.code.includes(query.toUpperCase())),
    [sessions, query]
  )
  const activeCount = sessions.filter((s) => s.status !== 'ended').length

  return (
    <div className="flex h-full">
      {/* LEFT RAIL */}
      <aside className="flex w-56 flex-shrink-0 flex-col border-r border-line bg-sidebar">
        <div className="px-5 py-5">
          <div className="mb-1 flex items-center gap-2">
            <Headphones className="h-5 w-5 text-signal" />
            <span className="text-sm font-semibold text-fg">Support</span>
          </div>
          <p className="text-xs leading-relaxed text-dim">
            Provide on-demand support for any device on the internet.
          </p>
        </div>
        <div className="px-4">
          <button className="btn-primary w-full justify-center" onClick={create}>
            <Plus className="h-4 w-4" /> Create
          </button>
        </div>
        <nav className="mt-4 px-3">
          <div className="nav-item nav-item-active justify-between">
            <span>My Sessions</span>
            <span className="rounded-full bg-signal/15 px-2 text-xs text-signal">{activeCount}</span>
          </div>
        </nav>
        <div className="mt-auto px-5 py-4">
          <div className="mb-2 flex items-center gap-2 text-xs text-dim">
            <span className={`h-2 w-2 rounded-full ${wsState === 'open' ? 'dot-online' : 'dot-offline'}`} />
            {wsState === 'open' ? 'Live' : 'Reconnecting…'}
          </div>
          <div className="truncate text-xs text-dim">{email}</div>
          <button className="mt-1 text-xs text-signal hover:underline" onClick={onSignOut}>Sign out</button>
        </div>
      </aside>

      {/* MIDDLE — session list */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <h1 className="text-lg font-semibold text-fg">My Sessions</h1>
          <div className="flex items-center gap-1">
            <button className="btn-ghost" onClick={() => sel && setSelected(sel.id)} title="Join"><LogIn className="h-4 w-4" /></button>
            <button className="btn-ghost" title="Edit"><Edit2 className="h-4 w-4" /></button>
            <button className="btn-ghost" onClick={() => sel && endSession(sel.id)} title="Delete"><Trash2 className="h-4 w-4" /></button>
            <button className="btn-ghost" title="More"><MoreHorizontal className="h-4 w-4" /></button>
            <button className="btn-ghost" onClick={refresh} title="Refresh"><RefreshCw className="h-4 w-4" /></button>
          </div>
        </div>
        <div className="px-6 py-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
            <input className="field pl-9" placeholder="Search My Sessions" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
        </div>
        <div className="flex-1 overflow-auto px-4">
          {filtered.length === 0 && <div className="px-2 py-8 text-center text-sm text-dim">No sessions yet. Click Create to start one.</div>}
          {filtered.map((s) => {
            const online = s.status === 'joined'
            return (
              <div key={s.id} onClick={() => setSelected(s.id)}
                className={`mb-1 cursor-pointer rounded-lg border px-4 py-3 ${selected === s.id ? 'border-signal bg-signal/5' : 'border-transparent hover:bg-sidebar'}`}>
                <div className="flex items-center justify-between">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-fg">{s.name}</div>
                    <div className="text-xs text-dim">Host: {s.host || '—'}</div>
                    <div className="text-xs text-dim">
                      User: {s.user || '—'} {online ? '(Active)' : '(Idle)'}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <User className="h-4 w-4 text-faint" />
                    <div className={`h-0.5 w-10 ${online ? 'bg-green-500' : 'bg-line'}`} />
                    <User className={`h-4 w-4 ${online ? 'text-green-500' : 'text-faint'}`} />
                  </div>
                </div>
                {online && <div className="mt-1 text-right text-xs text-green-600">Guest · connected</div>}
              </div>
            )
          })}
        </div>
      </div>

      {/* RIGHT — detail */}
      <aside className="flex w-96 flex-shrink-0 flex-col border-l border-line bg-card">
        {!sel ? (
          <div className="flex h-full items-center justify-center px-8 text-center text-sm text-dim">
            Select a session, or click Create to start a new one.
          </div>
        ) : (
          <div className="flex flex-col gap-4 p-6">
            <div>
              <label className="mb-1 block text-xs uppercase tracking-wide text-dim">Name</label>
              <input className="field" value={sel.name}
                onChange={(e) => setSessions((p) => p.map((x) => x.id === sel.id ? { ...x, name: e.target.value } : x))} />
            </div>

            <div>
              <div className="mb-2 text-xs uppercase tracking-wide text-dim">Invite via</div>
              <div className="flex gap-1 rounded-lg bg-sidebar p-1">
                <button onClick={() => setInvite('code')} className={`flex-1 rounded-md py-1.5 text-sm ${invite === 'code' ? 'bg-card font-semibold text-fg shadow-sm' : 'text-dim'}`}>Code</button>
                <button onClick={() => setInvite('link')} className={`flex-1 rounded-md py-1.5 text-sm ${invite === 'link' ? 'bg-card font-semibold text-fg shadow-sm' : 'text-dim'}`}>Link</button>
              </div>
            </div>

            {invite === 'code' ? (
              <div>
                <div className="mb-1 text-xs text-dim">Direct guest to:</div>
                <div className="mb-3 flex gap-2">
                  <input readOnly className="field text-xs" value={`${api}/join`} />
                  <button className="btn-ghost" onClick={() => copy(`${api}/join`, 'url')}>{copied === 'url' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}</button>
                </div>
                <div className="mb-1 text-xs text-dim">And instruct to type in the code:</div>
                <div className="flex gap-2">
                  <input readOnly className="field text-center text-2xl font-extrabold tracking-widest text-signal" value={sel.code} />
                  <button className="btn-ghost" onClick={() => copy(sel.code, 'code')}>{copied === 'code' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}</button>
                </div>
              </div>
            ) : (
              <div>
                <div className="mb-1 text-xs text-dim">Share this link:</div>
                <div className="flex gap-2">
                  <input readOnly className="field text-xs" value={sel.link} />
                  <button className="btn-ghost" onClick={() => copy(sel.link, 'link')}>{copied === 'link' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}</button>
                </div>
              </div>
            )}

            <button className="btn-primary w-full justify-center" onClick={refresh}>Join</button>

            <div className={`rounded-lg p-3 text-sm ${sel.status === 'joined' ? 'bg-green-50 text-green-700' : 'bg-sidebar text-dim'}`}>
              {sel.status === 'joined'
                ? '✓ Your guest has connected. Click Join to launch control.'
                : 'Waiting for your guest to connect…'}
            </div>

            <div className="rounded-lg border border-line bg-sidebar p-4 text-center text-xs text-dim">
              Screen preview appears here once connected.
            </div>
          </div>
        )}
      </aside>
    </div>
  )
}