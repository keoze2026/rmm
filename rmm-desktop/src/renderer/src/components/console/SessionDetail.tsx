import { useEffect, useRef, useState } from 'react'
import {
  Contact,
  Crosshair,
  Download,
  FileText,
  History,
  Hourglass,
  Info,
  MessageSquare,
  MoreHorizontal,
  Pencil,
  ScrollText,
  Terminal,
  Wrench
} from 'lucide-react'
import type { Machine } from '../../types'
import type { SupportSessionRow } from '../../useSupportSessions'
import { HistoryPanel, InfoPanel, LogsPanel, RemoteToolPanel, Unavailable } from './DetailPanels'
import { ScreenPreview } from './ScreenPreview'

export type TabKey =
  | 'session'
  | 'info'
  | 'history'
  | 'chat'
  | 'terminal'
  | 'files'
  | 'tools'
  | 'download'
  | 'logs'
  | 'locate'

const TABS: Array<{ key: TabKey; icon: typeof Info; title: string }> = [
  { key: 'session', icon: Contact, title: 'Session' },
  { key: 'info', icon: Info, title: 'System info' },
  { key: 'history', icon: History, title: 'Session history' },
  { key: 'chat', icon: MessageSquare, title: 'Chat' },
  { key: 'terminal', icon: Terminal, title: 'Command prompt' },
  { key: 'files', icon: FileText, title: 'File transfer' },
  { key: 'tools', icon: Wrench, title: 'Tools' },
  { key: 'download', icon: Download, title: 'Download files' },
  { key: 'logs', icon: ScrollText, title: 'Logs' },
  { key: 'locate', icon: Crosshair, title: 'Locate' }
]

interface Props {
  session: SupportSessionRow | null
  machine: Machine | null
  base: string
  token: string
  tab: TabKey
  onTab: (t: TabKey) => void
  /** Bumped by the Edit button to put the cursor in the Name field. */
  editNonce: number
  onRename: (id: string, name: string) => void
  onJoin: () => void
  joinError: string | null
  /** False while the full viewer is open, so only one session runs at a time. */
  showPreview: boolean
}

export function SessionDetail({
  session,
  machine,
  base,
  token,
  tab,
  onTab,
  editNonce,
  onRename,
  onJoin,
  joinError,
  showPreview
}: Props) {
  const [invite, setInvite] = useState<'code' | 'link'>('code')
  const [copied, setCopied] = useState('')
  const nameRef = useRef<HTMLInputElement>(null)

  // Edit means "name this session" — select the text so typing replaces it.
  useEffect(() => {
    if (!editNonce) return
    nameRef.current?.focus()
    nameRef.current?.select()
  }, [editNonce])

  if (!session) {
    return (
      <aside className="flex min-w-0 flex-1 items-center justify-center border-l border-line bg-surface px-10 text-center text-[13px] text-dim">
        Select a session, or click Create to start a new one.
      </aside>
    )
  }

  const joined = session.status === 'joined'
  // The guest goes to the site root and types the code; the link form carries
  // the token. Both come from the server's own link, so they stay correct.
  const joinBase = session.link.replace(/\/join\/.*$/, '/')

  function copy(text: string, which: string) {
    navigator.clipboard.writeText(text)
    setCopied(which)
    setTimeout(() => setCopied(''), 1500)
  }

  return (
    <aside className="flex min-w-0 flex-1 border-l border-line bg-surface">
      {/* Vertical tab rail */}
      <div className="flex w-[46px] flex-shrink-0 flex-col items-center border-r border-line bg-ink pt-[68px]">
        {TABS.map((t) => {
          const Icon = t.icon
          const active = tab === t.key
          return (
            <button
              key={t.key}
              title={t.title}
              onClick={() => onTab(t.key)}
              className={`flex h-10 w-full items-center justify-center border-l-[3px] transition-colors ${
                active
                  ? 'border-signal bg-surface text-signal'
                  : 'border-transparent text-dim hover:text-fg'
              }`}
            >
              <Icon className="h-[19px] w-[19px]" strokeWidth={1.7} />
            </button>
          )
        })}
      </div>

      {/* Panel body */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-[68px] flex-shrink-0 items-center px-8 text-[15px] text-fg">
          {session.name}
        </div>

        <div className="flex-1 overflow-auto">
          {tab === 'session' && (
            <div className="px-8 pb-10">
              {/* Name */}
              <label className="mb-1.5 block text-[13px] text-fg">Name:</label>
              <div className="relative mb-7">
                <input
                  ref={nameRef}
                  value={session.name}
                  onChange={(e) => onRename(session.id, e.target.value)}
                  className="w-full rounded border border-line bg-surface px-3 py-2 pr-9 text-[14px] text-fg focus:border-signal focus:outline-none"
                />
                <Pencil className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-dim" />
              </div>

              {/* Invite via */}
              <div className="mb-3 flex items-center justify-center gap-4 text-[13px]">
                <span className="italic text-dim">Invite via:</span>
                {(['code', 'link'] as const).map((k) => (
                  <button
                    key={k}
                    onClick={() => setInvite(k)}
                    className={`pb-1 capitalize ${
                      invite === k
                        ? 'border-b-2 border-signal font-medium text-signal'
                        : 'border-b-2 border-transparent text-fg hover:text-signal'
                    }`}
                  >
                    {k}
                  </button>
                ))}
              </div>

              {/* Invite card */}
              <div className="relative rounded border border-line px-6 py-5">
                <button
                  className="absolute right-3 top-3 text-dim hover:text-fg"
                  title={invite === 'code' ? 'Copy code' : 'Copy link'}
                  onClick={() => copy(invite === 'code' ? session.code : session.link, invite)}
                >
                  <MoreHorizontal className="h-[18px] w-[18px]" />
                </button>

                {invite === 'code' ? (
                  <>
                    <div className="mb-2 text-[13px] text-fg">Direct guest to:</div>
                    <div className="mb-4 text-center text-[15px] font-bold text-fg">{joinBase}</div>
                    <div className="mb-2 text-[13px] text-fg">And instruct to type in the code:</div>
                    <div className="relative">
                      <input
                        readOnly
                        value={session.code}
                        onClick={() => copy(session.code, 'code')}
                        className="w-full cursor-pointer rounded border border-line bg-surface px-3 py-2.5 pr-9 text-center text-[17px] font-bold tracking-wide text-fg"
                      />
                      <Pencil className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-dim" />
                    </div>
                  </>
                ) : (
                  <>
                    <div className="mb-2 text-[13px] text-fg">Send your guest this link:</div>
                    <input
                      readOnly
                      value={session.link}
                      onClick={() => copy(session.link, 'link')}
                      className="w-full cursor-pointer rounded border border-line bg-surface px-3 py-2.5 text-center text-[13px] text-fg"
                    />
                  </>
                )}
                {copied && (
                  <div className="mt-2 text-center text-[12px] text-online">Copied to clipboard</div>
                )}
              </div>

              {/* Join */}
              <div className="mt-7 flex justify-center">
                <button
                  onClick={onJoin}
                  disabled={!joined}
                  className="rounded bg-signal px-10 py-2.5 text-[15px] font-medium text-white transition-colors hover:bg-signalHover disabled:opacity-40"
                >
                  Join
                </button>
              </div>
              {joinError && (
                <div className="mt-3 text-center text-[12px] text-danger">{joinError}</div>
              )}

              {/* Waiting state */}
              <div className="mt-8">
                <div className="flex items-center gap-2">
                  <Hourglass className={`h-[18px] w-[18px] ${joined ? 'text-online' : 'text-dim'}`} />
                  <span className="text-[15px] text-fg">
                    {joined ? 'Your guest has joined.' : 'Your guest has not joined yet...'}
                  </span>
                </div>
                <p className="mt-1.5 text-[13px] italic leading-relaxed text-dim">
                  {joined
                    ? 'Click Join to launch the host client and control their screen.'
                    : 'Once you and your guest join the session, you can control their screen. Click Join to launch the host client.'}
                </p>
              </div>

              {joined && showPreview && session.machine_id && (
                <ScreenPreview
                  base={base}
                  token={token}
                  machineId={session.machine_id}
                  onOpen={onJoin}
                />
              )}
            </div>
          )}

          {tab === 'info' && <InfoPanel machine={machine} />}
          {tab === 'history' && <HistoryPanel base={base} token={token} machine={machine} />}
          {tab === 'logs' && <LogsPanel base={base} token={token} machine={machine} />}

          {tab === 'terminal' && (
            <RemoteToolPanel
              title="Command prompt"
              note="Opens a shell on the guest's computer inside the remote session — a real terminal on Mac and Linux, cmd.exe on Windows."
              canOpen={joined}
              onOpen={onJoin}
            />
          )}
          {tab === 'files' && (
            <RemoteToolPanel
              title="File transfer"
              note="Browse the guest's files and copy them in either direction. Runs with the permissions of the user the agent runs as."
              canOpen={joined}
              onOpen={onJoin}
            />
          )}
          {tab === 'download' && (
            <RemoteToolPanel
              title="Download files"
              note="Pull files from the guest's computer. Large files stream in chunks, so they don't have to fit in one message."
              canOpen={joined}
              onOpen={onJoin}
            />
          )}

          {tab === 'chat' && (
            <Unavailable
              title="Chat is not available"
              note="The endpoint agent has no chat command in its protocol, so this needs a change on the agent and server before it can work."
            />
          )}
          {tab === 'tools' && (
            <Unavailable
              title="Tools are not available"
              note="Task manager, services and registry access need new commands on the endpoint agent. Nothing here works without that."
            />
          )}
          {tab === 'locate' && (
            <Unavailable
              title="Locate is not available"
              note="Pointing at the guest's screen needs a new command on the endpoint agent before the console can request it."
            />
          )}
        </div>
      </div>
    </aside>
  )
}
