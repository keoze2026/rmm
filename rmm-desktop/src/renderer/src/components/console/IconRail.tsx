import { Bell, Headphones } from 'lucide-react'

interface Props {
  email: string
  wsState: string
  onSignOut: () => void
}

/**
 * Far-left rail: brand tile, the section nav, and the user cluster pinned to
 * the bottom — the fixed frame of the one-page console.
 */
export function IconRail({ email, wsState, onSignOut }: Props) {
  const initial = (email || '?').charAt(0).toUpperCase()

  return (
    <nav className="flex w-[74px] flex-shrink-0 flex-col items-center border-r border-line bg-surface">
      {/* Brand tile */}
      <div className="flex h-[68px] w-full items-center justify-center">
        <div className="flex h-[52px] w-[52px] items-center justify-center bg-signal">
          <svg viewBox="0 0 24 24" className="h-7 w-7" fill="none" stroke="#fff" strokeWidth="1.8">
            <rect x="2.5" y="4" width="19" height="13" rx="1.5" />
            <path d="M8 20h8M12 17v3" />
            <path d="M9.5 8.5h5M9.5 12h5" strokeLinecap="round" />
          </svg>
        </div>
      </div>

      {/* Sections — Support is the only one today */}
      <button
        className="flex w-full flex-col items-center gap-1 bg-ink py-3 text-signal"
        title="Support"
      >
        <Headphones className="h-[22px] w-[22px]" />
        <span className="text-[11px] font-medium">Support</span>
      </button>

      <div className="flex-1" />

      {/* User cluster */}
      <button
        className="mb-3 flex h-9 w-9 items-center justify-center rounded-full bg-ink text-dim hover:text-fg"
        title={wsState === 'open' ? 'Connected' : 'Reconnecting…'}
      >
        <Bell className="h-[18px] w-[18px]" />
        {wsState !== 'open' && (
          <span className="absolute mt-[-14px] ml-[14px] h-2 w-2 rounded-full bg-warn" />
        )}
      </button>
      <button
        onClick={onSignOut}
        title={`${email} — click to sign out`}
        className="mb-5 flex h-9 w-9 items-center justify-center rounded-full bg-signal text-sm font-semibold text-white hover:bg-signalHover"
      >
        {initial}
      </button>
    </nav>
  )
}
