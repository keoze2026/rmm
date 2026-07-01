import { useCallback, useEffect, useRef, useState } from 'react'
import { MousePointer2, EyeOff, X, Maximize2, TerminalSquare, FolderOpen } from 'lucide-react'
import { useRemoteSession, type SessionStatus } from '../useRemoteSession'
import { TerminalPanel } from './TerminalPanel'
import { FilesPanel } from './FilesPanel'
import type { Machine } from '../types'

interface Props {
  base: string
  token: string
  machine: Machine
  onClose: () => void
}

// Browser key names -> the agent's special-key vocabulary (input_control.py).
const SPECIAL: Record<string, string> = {
  Enter: 'enter',
  Tab: 'tab',
  Backspace: 'backspace',
  Delete: 'delete',
  Escape: 'esc',
  ArrowUp: 'up',
  ArrowDown: 'down',
  ArrowLeft: 'left',
  ArrowRight: 'right',
  Home: 'home',
  End: 'end',
  PageUp: 'pageup',
  PageDown: 'pagedown',
  Shift: 'shift',
  Control: 'ctrl',
  Alt: 'alt',
  Meta: 'cmd',
  CapsLock: 'capslock',
  ' ': 'space',
  F1: 'f1', F2: 'f2', F3: 'f3', F4: 'f4', F5: 'f5', F6: 'f6',
  F7: 'f7', F8: 'f8', F9: 'f9', F10: 'f10', F11: 'f11', F12: 'f12'
}

const BUTTONS = ['left', 'middle', 'right'] as const

const statusText: Record<SessionStatus, string> = {
  connecting: 'Connecting…',
  starting: 'Starting session…',
  live: 'Live',
  ended: 'Session ended',
  error: 'Error'
}

type Panel = 'none' | 'terminal' | 'files'

export function RemoteViewer({ base, token, machine, onClose }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null)
  const [control, setControl] = useState(true)
  const controlRef = useRef(control)
  controlRef.current = control

  // Which side panel is open. While a panel is open we stop forwarding the
  // keyboard to the remote screen so typing goes to the terminal/inputs.
  const [panel, setPanel] = useState<Panel>('none')
  const panelRef = useRef(panel)
  panelRef.current = panel

  // Latest pointer move, flushed once per animation frame to avoid flooding.
  const pendingMove = useRef<{ x: number; y: number } | null>(null)
  const rafRef = useRef<number | null>(null)

  // Message fan-out to the terminal/file panels.
  const listenersRef = useRef(new Set<(m: Record<string, unknown>) => void>())
  const onMessage = useCallback((m: Record<string, unknown>) => {
    listenersRef.current.forEach((fn) => fn(m))
  }, [])
  const subscribe = useCallback((fn: (m: Record<string, unknown>) => void) => {
    listenersRef.current.add(fn)
    return () => {
      listenersRef.current.delete(fn)
    }
  }, [])

  const drawFrame = useCallback((bitmap: ImageBitmap) => {
    const canvas = canvasRef.current
    if (!canvas) {
      bitmap.close()
      return
    }
    if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
      canvas.width = bitmap.width
      canvas.height = bitmap.height
    }
    let ctx = ctxRef.current
    if (!ctx) {
      ctx = canvas.getContext('2d')
      ctxRef.current = ctx
    }
    ctx?.drawImage(bitmap, 0, 0)
    bitmap.close()
  }, [])

  const { status, error, sendInput, sendCommand, stop } = useRemoteSession(
    base,
    token,
    machine.id,
    { onFrame: drawFrame, onMessage }
  )

  const close = useCallback(() => {
    stop()
    onClose()
  }, [stop, onClose])

  // ---- pointer helpers ----
  const norm = (e: { clientX: number; clientY: number }): { x: number; y: number } => {
    const canvas = canvasRef.current!
    const r = canvas.getBoundingClientRect()
    const x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width))
    const y = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))
    return { x, y }
  }

  const flushMove = useCallback(() => {
    rafRef.current = null
    const p = pendingMove.current
    if (p && controlRef.current) sendInput('mouse_move', p)
    pendingMove.current = null
  }, [sendInput])

  const onMove = (e: React.MouseEvent) => {
    if (!controlRef.current) return
    pendingMove.current = norm(e)
    if (rafRef.current == null) rafRef.current = requestAnimationFrame(flushMove)
  }
  const onDown = (e: React.MouseEvent) => {
    if (!controlRef.current) return
    e.preventDefault()
    sendInput('mouse_down', { ...norm(e), button: BUTTONS[e.button] ?? 'left' })
  }
  const onUp = (e: React.MouseEvent) => {
    if (!controlRef.current) return
    e.preventDefault()
    sendInput('mouse_up', { ...norm(e), button: BUTTONS[e.button] ?? 'left' })
  }
  const onWheel = (e: React.WheelEvent) => {
    if (!controlRef.current) return
    sendInput('mouse_scroll', { dx: -Math.sign(e.deltaX), dy: -Math.sign(e.deltaY) })
  }

  // ---- keyboard: capture at window while the viewer is open ----
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (!controlRef.current || panelRef.current !== 'none') return
      const special = SPECIAL[e.key]
      if (special) {
        e.preventDefault()
        sendInput('key_down', { key: special })
        return
      }
      if (e.key.length === 1) {
        e.preventDefault()
        if (e.ctrlKey || e.altKey || e.metaKey) {
          sendInput('key_down', { key: e.key.toLowerCase() })
        } else {
          // Type the exact character (handles shifted symbols/capitals).
          sendInput('key_type', { text: e.key })
        }
      }
    }
    const up = (e: KeyboardEvent) => {
      if (!controlRef.current || panelRef.current !== 'none') return
      const special = SPECIAL[e.key]
      if (special) {
        sendInput('key_up', { key: special })
        return
      }
      if (e.key.length === 1 && (e.ctrlKey || e.altKey || e.metaKey)) {
        sendInput('key_up', { key: e.key.toLowerCase() })
      }
    }
    window.addEventListener('keydown', down, true)
    window.addEventListener('keyup', up, true)
    return () => {
      window.removeEventListener('keydown', down, true)
      window.removeEventListener('keyup', up, true)
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
    }
  }, [sendInput])

  // Esc closes the viewer (does not reach the remote machine).
  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        close()
      }
    }
    window.addEventListener('keydown', onEsc)
    return () => window.removeEventListener('keydown', onEsc)
  }, [close])

  const requestFullscreen = () => {
    canvasRef.current?.parentElement?.requestFullscreen?.()
  }

  const togglePanel = (p: Panel) => setPanel((cur) => (cur === p ? 'none' : p))

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-ink">
      <div className="flex items-center justify-between border-b border-line bg-surface px-4 py-2">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-fg">{machine.name}</span>
          <StatusPill status={status} />
          {error && <span className="text-xs text-warn">{error}</span>}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setControl((c) => !c)}
            className="btn-ghost"
            title={control ? 'Switch to view-only' : 'Take control'}
          >
            {control ? <MousePointer2 className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
            {control ? 'Controlling' : 'View only'}
          </button>
          <button
            onClick={() => togglePanel('terminal')}
            className={panel === 'terminal' ? 'btn-primary' : 'btn-ghost'}
            title="Remote terminal"
          >
            <TerminalSquare className="h-4 w-4" />
            Terminal
          </button>
          <button
            onClick={() => togglePanel('files')}
            className={panel === 'files' ? 'btn-primary' : 'btn-ghost'}
            title="Files"
          >
            <FolderOpen className="h-4 w-4" />
            Files
          </button>
          <button onClick={requestFullscreen} className="btn-ghost" title="Fullscreen">
            <Maximize2 className="h-4 w-4" />
          </button>
          <button onClick={close} className="btn-ghost" title="End session (Esc)">
            <X className="h-4 w-4" />
            End
          </button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col">
        <div className="relative flex flex-1 items-center justify-center overflow-hidden bg-black">
          <canvas
            ref={canvasRef}
            onMouseMove={onMove}
            onMouseDown={onDown}
            onMouseUp={onUp}
            onWheel={onWheel}
            onContextMenu={(e) => e.preventDefault()}
            className="max-h-full max-w-full object-contain"
            style={{ cursor: control ? 'crosshair' : 'default', imageRendering: 'auto' }}
          />
          {status !== 'live' && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="rounded-md border border-line bg-surface/90 px-4 py-3 text-sm text-dim">
                {error ?? statusText[status]}
              </div>
            </div>
          )}
        </div>

        {panel !== 'none' && (
          <div className="h-2/5 min-h-[200px] border-t border-line">
            {panel === 'terminal' ? (
              <TerminalPanel sendCommand={sendCommand} subscribe={subscribe} />
            ) : (
              <FilesPanel sendCommand={sendCommand} subscribe={subscribe} />
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function StatusPill({ status }: { status: SessionStatus }) {
  const color =
    status === 'live'
      ? 'text-online'
      : status === 'error'
        ? 'text-warn'
        : status === 'ended'
          ? 'text-faint'
          : 'text-warn'
  return (
    <span className={`flex items-center gap-1.5 font-mono text-xs ${color}`}>
      <span className="inline-block h-1.5 w-1.5 rounded-full bg-current" />
      {statusText[status]}
    </span>
  )
}