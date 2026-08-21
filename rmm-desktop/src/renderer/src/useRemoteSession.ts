import { useCallback, useEffect, useRef, useState } from 'react'
import { adminWsUrl } from './api'

export type SessionStatus = 'connecting' | 'starting' | 'live' | 'ended' | 'error'

interface Options {
  onFrame: (bitmap: ImageBitmap) => void
  // Phase 6: receive non-frame messages (terminal_output, file_chunk, agent_event)
  // so the terminal and file panels can react to them.
  onMessage?: (msg: Record<string, unknown>) => void
}

interface RemoteSession {
  status: SessionStatus
  error: string | null
  sendInput: (action: string, payload: Record<string, unknown>) => void
  sendCommand: (action: string, payload: Record<string, unknown>) => void
  stop: () => void
}

/**
 * Opens a dedicated admin WebSocket for one machine: subscribes (so the server
 * routes that machine's frames here), starts a control session, decodes the
 * agent's JPEG frames to ImageBitmaps, and forwards admin input back. Closing
 * stops the session and tears the socket down.
 */
export function useRemoteSession(
  base: string,
  token: string,
  machineId: string,
  { onFrame, onMessage }: Options
): RemoteSession {
  const [status, setStatus] = useState<SessionStatus>('connecting')
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const decodingRef = useRef(false)
  const pendingB64Ref = useRef<string | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const liveRef = useRef(false)
  const onFrameRef = useRef(onFrame)
  onFrameRef.current = onFrame
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  // Decode latest-only: if frames arrive faster than we decode, drop stale ones.
  const decode = useCallback(async (b64: string) => {
    if (decodingRef.current) {
      pendingB64Ref.current = b64
      return
    }
    decodingRef.current = true
    try {
      const bin = atob(b64)
      const bytes = new Uint8Array(bin.length)
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
      const blob = new Blob([bytes], { type: 'image/jpeg' })
      const bitmap = await createImageBitmap(blob)
      onFrameRef.current(bitmap)
    } catch {
      // ignore a bad frame
    } finally {
      decodingRef.current = false
      const next = pendingB64Ref.current
      pendingB64Ref.current = null
      if (next) void decode(next)
    }
  }, [])

  const send = useCallback((msg: Record<string, unknown>) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg))
  }, [])

  const sendInput = useCallback(
    (action: string, payload: Record<string, unknown>) => {
      send({ type: 'command', machine_id: machineId, action, payload })
    },
    [send, machineId]
  )

  const stop = useCallback(() => {
    send({ type: 'command', machine_id: machineId, action: 'session_stop' })
    send({ type: 'unsubscribe', machine_id: machineId })
    setStatus('ended')
    wsRef.current?.close()
  }, [send, machineId])

  useEffect(() => {
    setStatus('connecting')
    setError(null)
    liveRef.current = false
    const ws = new WebSocket(adminWsUrl(base, token))
    wsRef.current = ws

    const stopMsg = JSON.stringify({
      type: 'command',
      machine_id: machineId,
      action: 'session_stop'
    })
    const startMsg = JSON.stringify({
      type: 'command',
      machine_id: machineId,
      action: 'session_start',
      payload: { kind: 'control' }
    })

    ws.onopen = () => {
      setStatus('starting')
      ws.send(JSON.stringify({ type: 'subscribe', machine_id: machineId }))
      // The agent's start_session() returns early when a session is already
      // active and never re-emits session_started, so a session left behind by
      // an untidy disconnect would leave us stuck on 'starting' forever. Clear
      // first, then start.
      ws.send(stopMsg)
      ws.send(startMsg)
      // If session_started still hasn't landed, clear and start once more.
      retryRef.current = setTimeout(() => {
        if (ws.readyState !== WebSocket.OPEN) return
        ws.send(stopMsg)
        ws.send(startMsg)
      }, 3500)
    }

    ws.onmessage = (ev) => {
      let msg: Record<string, unknown>
      try {
        msg = JSON.parse(ev.data as string)
      } catch {
        return
      }
      if (msg.machine_id && msg.machine_id !== machineId) return

      switch (msg.type) {
        case 'frame':
          void decode(msg.data as string)
          break
        case 'agent_event':
          if (msg.event === 'session_started') {
            liveRef.current = true
            if (retryRef.current) clearTimeout(retryRef.current)
            setStatus('live')
          } else if (msg.event === 'session_ended') {
            // The session_ended from our own pre-start cleanup must not be
            // mistaken for the session we are in the middle of opening.
            if (liveRef.current) setStatus('ended')
          } else if (msg.event === 'session_error') {
            setStatus('error')
            setError((msg.reason as string) || 'The agent could not start the session.')
          }
          break
        case 'command_failed':
          setStatus('error')
          setError(
            msg.reason === 'agent_offline'
              ? 'This machine went offline.'
              : `Command failed: ${String(msg.reason)}`
          )
          break
        default:
          break
      }

      // Hand every message to the panels (terminal_output, file_chunk, agent_event…).
      onMessageRef.current?.(msg)
    }

    ws.onerror = () => {
      // A socket we've already replaced (StrictMode double-mounts effects in
      // dev, and its aborted first socket errors after the real one is up).
      if (wsRef.current !== ws) return
      setStatus('error')
      setError('Connection error. Check the server and try again.')
    }

    ws.onclose = () => {
      if (wsRef.current !== ws) return
      setStatus((s) => (s === 'error' ? s : 'ended'))
    }

    return () => {
      if (retryRef.current) clearTimeout(retryRef.current)
      // Best-effort stop on unmount.
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'command', machine_id: machineId, action: 'session_stop' }))
        ws.send(JSON.stringify({ type: 'unsubscribe', machine_id: machineId }))
      }
      ws.close()
    }
  }, [base, token, machineId, decode])

  return { status, error, sendInput, sendCommand: sendInput, stop }
}