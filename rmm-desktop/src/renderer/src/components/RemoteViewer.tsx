import { useCallback, useEffect, useRef, useState } from 'react'
import { MousePointer2, EyeOff, X, Maximize2, TerminalSquare, FolderOpen,
  Camera, ZoomIn, ZoomOut, Pencil, Eraser, Upload, Download, Monitor } from 'lucide-react'
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

  // --- added features: zoom, annotation, monitors ------------------------
  const [zoom, setZoom] = useState(1)
  const [annotating, setAnnotating] = useState(false)
  const annotatingRef = useRef(annotating)
  annotatingRef.current = annotating
  const overlayRef = useRef<HTMLCanvasElement | null>(null)
  const drawingRef = useRef(false)
  const [fileStatus, setFileStatus] = useState<string>('')
  const [stats, setStats] = useState<{ fps: number; kbps: number }>({ fps: 0, kbps: 0 })
  const statRef = useRef({ frames: 0, bytes: 0 })
  const [monitors, setMonitors] = useState<Array<Record<string, number>>>([])
  const [currentMonitor, setCurrentMonitor] = useState<number | null>(null)
  const [showMonitors, setShowMonitors] = useState(false)
  const uploadInputRef = useRef<HTMLInputElement | null>(null)

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

  // --- added: consume the new agent replies, via the existing subscribe ---
  const transfersRef = useRef<Record<string, { chunks: string[]; name: string }>>({})

  useEffect(() => {
    return subscribe((m) => {
      if (m.type === 'frame') {
        statRef.current.frames += 1
        statRef.current.bytes += Math.floor(String(m.data ?? '').length * 0.75)
      }
      if (m.type === 'agent_event') {
        if (m.event === 'fs_write_done') {
          setFileStatus(`Sent to guest: ${String(m.path ?? '')}`)
          setTimeout(() => setFileStatus(''), 6000)
        } else if (m.event === 'fs_error') {
          setFileStatus(`File error: ${String(m.reason ?? 'failed')}`)
          setTimeout(() => setFileStatus(''), 8000)
        } else if (m.event === 'monitors') {
          setMonitors((m.monitors as Array<Record<string, number>>) ?? [])
          setCurrentMonitor((m.current as number) ?? null)
        } else if (m.event === 'monitor_selected' && m.ok) {
          setCurrentMonitor((m.index as number) ?? null)
        }
        return
      }
      if (m.type === 'file_chunk') {
        const id = String(m.transfer_id ?? '')
        const t = transfersRef.current[id]
        if (!t) return
        if (m.data) t.chunks.push(String(m.data))
        if (m.eof) {
          const bytes: number[] = []
          for (const c of t.chunks) {
            const bin = atob(c)
            for (let i = 0; i < bin.length; i++) bytes.push(bin.charCodeAt(i))
          }
          const url = URL.createObjectURL(new Blob([new Uint8Array(bytes)]))
          const a = document.createElement('a')
          a.href = url
          a.download = t.name || 'download'
          a.click()
          setTimeout(() => URL.revokeObjectURL(url), 5000)
          delete transfersRef.current[id]
        }
      }
    })
  }, [subscribe])

  // Live throughput readout: turns "it feels slow" into numbers.
  useEffect(() => {
    const t = setInterval(() => {
      const { frames, bytes } = statRef.current
      statRef.current = { frames: 0, bytes: 0 }
      setStats({ fps: frames, kbps: Math.round((bytes * 8) / 1000) })
    }, 1000)
    return () => clearInterval(t)
  }, [])

  // Keep the annotation layer matched to its box.
  useEffect(() => {
    const c = overlayRef.current
    if (!c) return
    const resize = () => {
      c.width = c.clientWidth
      c.height = c.clientHeight
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(c)
    return () => ro.disconnect()
  }, [])

  // --- added: save the current frame to a file --------------------------
  const saveScreenshot = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    canvas.toBlob((blob) => {
      if (!blob) return
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const stamp = new Date().toISOString().replace(/[:.]/g, '-')
      a.href = url
      a.download = `${machine.name}-${stamp}.png`
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 5000)
    }, 'image/png')
  }, [machine.name])

  // --- added: annotation overlay ----------------------------------------
  // Kept on its own canvas above the frame, so incoming frames never erase it.
  const overlayPos = useCallback((e: React.MouseEvent) => {
    const c = overlayRef.current
    if (!c) return null
    const r = c.getBoundingClientRect()
    return { x: ((e.clientX - r.left) / r.width) * c.width, y: ((e.clientY - r.top) / r.height) * c.height }
  }, [])

  const drawStart = useCallback((e: React.MouseEvent) => {
    const c = overlayRef.current
    const p = overlayPos(e)
    if (!c || !p) return
    drawingRef.current = true
    const ctx = c.getContext('2d')
    if (!ctx) return
    ctx.strokeStyle = '#EF4444'
    ctx.lineWidth = 3
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.beginPath()
    ctx.moveTo(p.x, p.y)
  }, [overlayPos])

  const drawMove = useCallback((e: React.MouseEvent) => {
    if (!drawingRef.current) return
    const c = overlayRef.current
    const p = overlayPos(e)
    if (!c || !p) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    ctx.lineTo(p.x, p.y)
    ctx.stroke()
  }, [overlayPos])

  const drawEnd = useCallback(() => {
    drawingRef.current = false
  }, [])

  const clearAnnotations = useCallback(() => {
    const c = overlayRef.current
    const ctx = c?.getContext('2d')
    if (c && ctx) ctx.clearRect(0, 0, c.width, c.height)
  }, [])

  // --- added: file to / from the guest, over the existing fs_* actions ----
  const sendFileToGuest = useCallback(
    async (file: File) => {
      const CHUNK = 192 * 1024 // keep each message well under the 16MB cap
      const buf = new Uint8Array(await file.arrayBuffer())
      // Land on the guest's desktop so they can see it arrive.
      const path = `~/Desktop/${file.name}`
      setFileStatus(`Sending ${file.name}…`)
      let first = true
      for (let off = 0; off < buf.length || first; off += CHUNK) {
        const slice = buf.subarray(off, off + CHUNK)
        let bin = ''
        for (let i = 0; i < slice.length; i++) bin += String.fromCharCode(slice[i])
        const last = off + CHUNK >= buf.length
        sendCommand('fs_write', { path, data: btoa(bin), first, last })
        first = false
        if (last) break
      }
    },
    [sendCommand]
  )

  const requestFileFromGuest = useCallback(() => {
    const path = window.prompt('Path of the file on the guest to download:')
    if (!path) return
    const id = `dl-${Date.now()}`
    transfersRef.current[id] = { chunks: [], name: path.split(/[\\/]/).pop() || 'download' }
    sendCommand('fs_read', { path, transfer_id: id })
  }, [sendCommand])

  // --- added: monitor switching -----------------------------------------
  const askMonitors = useCallback(() => {
    setShowMonitors((v) => !v)
    sendCommand('monitors_list', {})
  }, [sendCommand])

  const pickMonitor = useCallback(
    (index: number) => {
      sendCommand('monitor_select', { index })
      setShowMonitors(false)
    },
    [sendCommand]
  )

  const togglePanel = (p: Panel) => setPanel((cur) => (cur === p ? 'none' : p))

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-ink">
      <div className="flex items-center justify-between border-b border-line bg-surface px-4 py-2">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-fg">{machine.name}</span>
          <StatusPill status={status} />
          {error && <span className="text-xs text-warn">{error}</span>}
          {fileStatus && <span className="text-xs text-signal">{fileStatus}</span>}
          {status === 'live' && (
            <span className="font-mono text-xs text-dim">
              {stats.fps} fps · {stats.kbps > 1000 ? `${(stats.kbps / 1000).toFixed(1)} Mbps` : `${stats.kbps} kbps`}
            </span>
          )}
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
          {/* --- added features: screenshot, monitors, zoom, annotate, files --- */}
          <button onClick={saveScreenshot} className="btn-ghost" title="Save screenshot">
            <Camera className="h-4 w-4" />
          </button>

          <div className="relative">
            <button
              onClick={askMonitors}
              className={showMonitors ? 'btn-primary' : 'btn-ghost'}
              title="Choose display"
            >
              <Monitor className="h-4 w-4" />
              {currentMonitor != null ? `#${currentMonitor}` : ''}
            </button>
            {showMonitors && (
              <div className="absolute right-0 z-10 mt-1 w-56 rounded-lg border border-line bg-surface p-1 shadow-cardHover">
                {monitors.length === 0 && (
                  <div className="px-3 py-2 text-xs text-dim">Asking the agent…</div>
                )}
                {monitors.map((m) => (
                  <button
                    key={m.index}
                    onClick={() => pickMonitor(m.index)}
                    className={`flex w-full items-center justify-between rounded px-3 py-1.5 text-left text-xs hover:bg-ink ${
                      m.index === currentMonitor ? 'text-signal' : 'text-fg'
                    }`}
                  >
                    <span>{m.all ? 'All displays' : `Display ${m.index}`}</span>
                    <span className="text-dim">
                      {m.width}×{m.height}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={() => setZoom((z) => Math.min(4, +(z + 0.25).toFixed(2)))}
            className="btn-ghost"
            title="Zoom in"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
          <button
            onClick={() => setZoom((z) => Math.max(0.25, +(z - 0.25).toFixed(2)))}
            className="btn-ghost"
            title="Zoom out"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          {zoom !== 1 && (
            <button onClick={() => setZoom(1)} className="btn-ghost" title="Reset zoom">
              {Math.round(zoom * 100)}%
            </button>
          )}

          <button
            onClick={() => setAnnotating((a) => !a)}
            className={annotating ? 'btn-primary' : 'btn-ghost'}
            title="Draw on screen"
          >
            <Pencil className="h-4 w-4" />
          </button>
          {annotating && (
            <button onClick={clearAnnotations} className="btn-ghost" title="Clear drawing">
              <Eraser className="h-4 w-4" />
            </button>
          )}

          <button
            onClick={() => uploadInputRef.current?.click()}
            className="btn-ghost"
            title="Send a file to the guest (lands in their home folder)"
          >
            <Upload className="h-4 w-4" />
          </button>
          <button onClick={requestFileFromGuest} className="btn-ghost" title="Get a file from the guest">
            <Download className="h-4 w-4" />
          </button>
          <input
            ref={uploadInputRef}
            type="file"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) void sendFileToGuest(f)
              e.target.value = ''
            }}
          />

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
            style={{
              cursor: 'default',
              imageRendering: 'auto',
              // added: 1 by default, so the untouched view renders identically
              transform: `scale(${zoom})`,
              transformOrigin: 'center center'
            }}
          />
          {/* added: annotation layer. pointer-events off unless the pen is on,
              so the remote pointer/keyboard path is untouched when idle. */}
          <canvas
            ref={overlayRef}
            onMouseDown={drawStart}
            onMouseMove={drawMove}
            onMouseUp={drawEnd}
            onMouseLeave={drawEnd}
            className="absolute inset-0 h-full w-full"
            style={{ pointerEvents: annotating ? 'auto' : 'none', cursor: annotating ? 'crosshair' : 'default' }}
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