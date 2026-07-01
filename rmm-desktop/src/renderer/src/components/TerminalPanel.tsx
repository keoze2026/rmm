import { useEffect, useRef } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'

type SendCommand = (action: string, payload: Record<string, unknown>) => void
type Subscribe = (fn: (msg: Record<string, unknown>) => void) => () => void

interface Props {
  sendCommand: SendCommand
  subscribe: Subscribe
}

const TERM_ID = 'default'

function b64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

export function TerminalPanel({ sendCommand, subscribe }: Props) {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const termRef = useRef<Terminal | null>(null)
  const fitRef = useRef<FitAddon | null>(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    const term = new Terminal({
      fontFamily: '"JetBrains Mono", ui-monospace, monospace',
      fontSize: 13,
      cursorBlink: true,
      theme: { background: '#0B0F14', foreground: '#E6EDF3', cursor: '#35C2D8' }
    })
    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(host)
    fit.fit()
    termRef.current = term
    fitRef.current = fit

    // Forward what the admin types to the remote shell.
    const dataSub = term.onData((data) => {
      sendCommand('term_input', { term_id: TERM_ID, data })
    })

    // Receive shell output + lifecycle events for this terminal.
    const unsub = subscribe((msg) => {
      if (msg.type === 'terminal_output' && msg.term_id === TERM_ID) {
        term.write(b64ToBytes(msg.data as string))
      } else if (msg.type === 'agent_event') {
        if (msg.event === 'term_error' && msg.term_id === TERM_ID) {
          term.write(`\r\n\x1b[31m[terminal error: ${String(msg.reason)}]\x1b[0m\r\n`)
        } else if (msg.event === 'error' && msg.reason === 'no_active_session') {
          term.write('\r\n\x1b[33m[session not active]\x1b[0m\r\n')
        }
      }
    })

    // Start the shell sized to the panel.
    fit.fit()
    sendCommand('term_start', { term_id: TERM_ID, cols: term.cols, rows: term.rows })

    // Keep the PTY sized to the panel as it resizes.
    const ro = new ResizeObserver(() => {
      try {
        fit.fit()
        sendCommand('term_resize', { term_id: TERM_ID, cols: term.cols, rows: term.rows })
      } catch {
        // panel hidden / zero size — ignore
      }
    })
    ro.observe(host)
    term.focus()

    return () => {
      ro.disconnect()
      dataSub.dispose()
      unsub()
      sendCommand('term_stop', { term_id: TERM_ID })
      term.dispose()
      termRef.current = null
      fitRef.current = null
    }
  }, [sendCommand, subscribe])

  return <div ref={hostRef} className="h-full w-full bg-ink p-1" />
}