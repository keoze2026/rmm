import { useCallback, useEffect, useRef, useState } from 'react'
import { adminWsUrl, listMachines } from './api'
import type { Machine, WsInbound, WsState } from './types'

interface UseMachines {
  machines: Machine[]
  wsState: WsState
  error: string | null
  refresh: () => void
}

/**
 * Seeds the machine list from REST (full inventory) then keeps it live over the
 * admin WebSocket: machines_snapshot replaces the set, machine_status flips a
 * dot, machine_inventory merges reported fields. Reconnects with backoff.
 */
export function useMachines(base: string, token: string): UseMachines {
  const [byId, setById] = useState<Map<string, Machine>>(new Map())
  const [wsState, setWsState] = useState<WsState>('connecting')
  const [error, setError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const backoffRef = useRef(1000)
  const closedRef = useRef(false)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const merge = useCallback((id: string, patch: Partial<Machine>) => {
    setById((prev) => {
      const next = new Map(prev)
      const current = next.get(id)
      if (current) next.set(id, { ...current, ...patch })
      return next
    })
  }, [])

  const refresh = useCallback(() => {
    listMachines(base, token)
      .then((list) => {
        setById(new Map(list.map((m) => [m.id, m])))
        setError(null)
      })
      .catch((e) => setError(e?.message ?? 'Failed to load machines'))
  }, [base, token])

  useEffect(() => {
    closedRef.current = false
    refresh()

    const connect = () => {
      if (closedRef.current) return
      setWsState('connecting')
      const ws = new WebSocket(adminWsUrl(base, token))
      wsRef.current = ws

      ws.onopen = () => {
        setWsState('open')
        backoffRef.current = 1000
      }

      ws.onmessage = (ev) => {
        let msg: WsInbound
        try {
          msg = JSON.parse(ev.data as string)
        } catch {
          return
        }
        switch (msg.type) {
          case 'machines_snapshot': {
            const rows = (msg as Extract<WsInbound, { type: 'machines_snapshot' }>).machines
            setById((prev) => {
              const next = new Map<string, Machine>()
              for (const r of rows) {
                const existing = prev.get(r.id)
                next.set(r.id, {
                  ...(existing ?? blankMachine(r.id, r.name)),
                  name: r.name,
                  is_online: r.is_online,
                  os_name: r.os_name,
                  hostname: r.hostname,
                  ip_address: r.ip_address,
                  last_seen_at: r.last_seen_at
                })
              }
              return next
            })
            break
          }
          case 'machine_status': {
            const m = msg as Extract<WsInbound, { type: 'machine_status' }>
            merge(m.machine_id, {
              is_online: m.online,
              last_seen_at: new Date().toISOString()
            })
            break
          }
          case 'machine_inventory': {
            const m = msg as Extract<WsInbound, { type: 'machine_inventory' }>
            const inv = m.inventory as Partial<Machine>
            merge(m.machine_id, {
              hostname: (inv.hostname as string) ?? undefined,
              os_name: (inv.os_name as string) ?? undefined,
              os_version: (inv.os_version as string) ?? undefined,
              os_username: (inv.os_username as string) ?? undefined,
              cpu_model: (inv.cpu_model as string) ?? undefined,
              cpu_cores: (inv.cpu_cores as number) ?? undefined,
              ram_total_mb: (inv.ram_total_mb as number) ?? undefined,
              agent_version: (inv.agent_version as string) ?? undefined
            })
            break
          }
          default:
            break
        }
      }

      ws.onerror = () => {
        // onclose will follow and trigger the reconnect path.
      }

      ws.onclose = () => {
        setWsState('closed')
        if (closedRef.current) return
        const wait = Math.min(backoffRef.current, 15000)
        reconnectTimer.current = setTimeout(connect, wait)
        backoffRef.current = Math.min(backoffRef.current * 2, 15000)
      }
    }

    connect()

    return () => {
      closedRef.current = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [base, token, merge, refresh])

  return {
    machines: Array.from(byId.values()).sort((a, b) => a.name.localeCompare(b.name)),
    wsState,
    error,
    refresh
  }
}

function blankMachine(id: string, name: string): Machine {
  return {
    id,
    name,
    hostname: null,
    os_name: null,
    os_version: null,
    os_username: null,
    ip_address: null,
    cpu_model: null,
    cpu_cores: null,
    ram_total_mb: null,
    agent_version: null,
    notes: null,
    is_enabled: true,
    is_online: false,
    last_seen_at: null
  }
}
