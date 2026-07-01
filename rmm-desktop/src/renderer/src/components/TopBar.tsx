import { Radio, LogOut } from 'lucide-react'
import type { WsState } from '../types'

interface Props {
  email: string
  online: number
  total: number
  wsState: WsState
  onSignOut: () => void
}

const wsLabel: Record<WsState, string> = {
  connecting: 'connecting',
  open: 'live',
  closed: 'reconnecting'
}

const wsColor: Record<WsState, string> = {
  connecting: 'text-warn',
  open: 'text-online',
  closed: 'text-warn'
}

export function TopBar({ email, online, total, wsState, onSignOut }: Props) {
  return (
    <header className="flex items-center justify-between border-b border-line bg-surface px-6 py-3">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-signal/15 text-signal">
          <Radio className="h-4 w-4" />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-fg">RMM Console</div>
          <div className="font-mono text-[11px] text-faint">
            <span className="text-online">{online}</span>
            <span className="text-faint"> / {total} online</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-5">
        <span className={`flex items-center gap-1.5 font-mono text-xs ${wsColor[wsState]}`}>
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-current" />
          {wsLabel[wsState]}
        </span>
        <span className="text-xs text-dim">{email}</span>
        <button
          onClick={onSignOut}
          className="flex items-center gap-1.5 text-xs text-faint hover:text-fg"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </header>
  )
}
