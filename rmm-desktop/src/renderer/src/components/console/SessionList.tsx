import { ChevronDown, MoreHorizontal, Pencil, Plug, Search, Trash2, User } from 'lucide-react'
import type { SupportSessionRow } from '../../useSupportSessions'

interface Props {
  sessions: SupportSessionRow[]
  selectedId: string | null
  checked: Set<string>
  query: string
  hostLabel: string
  loading: boolean
  onSelect: (id: string) => void
  onToggleCheck: (id: string) => void
  onToggleAll: () => void
  onQuery: (q: string) => void
  onJoin: () => void
  onEdit: () => void
  onDelete: () => void
  onMore: () => void
}

function ToolbarButton({
  icon: Icon,
  label,
  onClick,
  disabled
}: {
  icon: typeof Plug
  label: string
  onClick: () => void
  disabled?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-1.5 px-2 py-1 text-[14px] text-fg transition-opacity hover:opacity-70 disabled:opacity-30"
    >
      <Icon className="h-[18px] w-[18px]" strokeWidth={1.7} />
      {label}
    </button>
  )
}

/** Third column: the session list with its toolbar, select-all and search. */
export function SessionList({
  sessions,
  selectedId,
  checked,
  query,
  hostLabel,
  loading,
  onSelect,
  onToggleCheck,
  onToggleAll,
  onQuery,
  onJoin,
  onEdit,
  onDelete,
  onMore
}: Props) {
  const allChecked = sessions.length > 0 && checked.size === sessions.length
  const hasSelection = selectedId !== null

  return (
    <section className="flex w-[420px] min-w-0 flex-shrink-0 flex-col border-r border-line bg-surface">
      {/* Header + toolbar */}
      <div className="flex h-[68px] items-center justify-between px-6">
        <h2 className="text-[19px] font-normal text-fg">My Sessions</h2>
        <div className="flex items-center gap-1">
          <ToolbarButton icon={Plug} label="Join" onClick={onJoin} disabled={!hasSelection} />
          <ToolbarButton icon={Pencil} label="Edit" onClick={onEdit} disabled={!hasSelection} />
          <ToolbarButton icon={Trash2} label="Delete" onClick={onDelete} disabled={!hasSelection} />
          <ToolbarButton icon={MoreHorizontal} label="More" onClick={onMore} />
        </div>
      </div>

      {/* Select-all + search */}
      <div className="flex items-center justify-between px-6 pb-4">
        <button onClick={onToggleAll} className="flex items-center gap-1 text-dim hover:text-fg">
          <span
            className={`flex h-[15px] w-[15px] items-center justify-center border ${
              allChecked ? 'border-signal bg-signal' : 'border-edge bg-surface'
            }`}
          >
            {allChecked && (
              <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" fill="none" stroke="#fff" strokeWidth="2.5">
                <path d="M2 6.5L4.5 9L10 3.5" />
              </svg>
            )}
          </span>
          <ChevronDown className="h-4 w-4" />
        </button>

        <div className="relative w-[230px]">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
          <input
            value={query}
            onChange={(e) => onQuery(e.target.value)}
            placeholder="Search My Sessions"
            className="w-full rounded-full border border-line bg-surface py-1.5 pl-8 pr-3 text-[13px] text-fg placeholder:text-faint focus:border-signal focus:outline-none"
          />
        </div>
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-auto border-t border-line">
        {loading && sessions.length === 0 && (
          <div className="px-6 py-10 text-center text-[13px] text-dim">Loading…</div>
        )}
        {!loading && sessions.length === 0 && (
          <div className="px-6 py-10 text-center text-[13px] text-dim">
            No sessions yet. Click Create to start one.
          </div>
        )}

        {sessions.map((s) => {
          const joined = s.status === 'joined'
          const active = s.id === selectedId
          return (
            <div
              key={s.id}
              onClick={() => onSelect(s.id)}
              className={`flex cursor-pointer items-center gap-3 border-b border-line px-6 py-3 ${
                active ? 'bg-ink' : 'hover:bg-ink/60'
              }`}
            >
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onToggleCheck(s.id)
                }}
                className={`flex h-[15px] w-[15px] flex-shrink-0 items-center justify-center border ${
                  checked.has(s.id) ? 'border-signal bg-signal' : 'border-edge bg-surface'
                }`}
              >
                {checked.has(s.id) && (
                  <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" fill="none" stroke="#fff" strokeWidth="2.5">
                    <path d="M2 6.5L4.5 9L10 3.5" />
                  </svg>
                )}
              </button>

              <div className="min-w-0 flex-1">
                <div className="truncate text-[14px] font-semibold text-fg">{s.name}</div>
                <div className="text-[12px] text-dim">Host: {hostLabel}</div>
              </div>

              {/* host ── guest connection indicator */}
              <div className="flex flex-shrink-0 items-center gap-1">
                <User className="h-[18px] w-[18px] text-dim" strokeWidth={1.7} />
                <span className="h-[3px] w-[52px] rounded-full bg-edge" />
                <span
                  className={`h-[3px] w-[52px] rounded-full ${joined ? 'bg-online' : 'bg-edge'}`}
                />
                <User
                  className={`h-[18px] w-[18px] ${joined ? 'text-online' : 'text-faint'}`}
                  strokeWidth={1.7}
                />
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
