import { useCallback, useEffect, useRef, useState } from 'react'
import { normalizeBase } from './api'

/** A support session as the console shows it. Mirrors the server's SupportOut. */
export interface SupportSessionRow {
  id: string
  code: string
  link: string
  name: string
  status: string // waiting | joined | ended
  machine_id: string | null
  joined_at: string | null
}

interface UseSupportSessions {
  sessions: SupportSessionRow[]
  loading: boolean
  error: string | null
  refresh: () => void
  create: () => Promise<SupportSessionRow | null>
  end: (id: string) => Promise<void>
  rename: (id: string, name: string) => void
}

/**
 * Polls /api/support/list and exposes create/end. Uses exactly the endpoints
 * the console already called — no new server contract.
 *
 * Names are local to this machine: the server stores a `label` column but
 * exposes no route to set it, so a rename here is cosmetic and resets when the
 * app restarts.
 */
export function useSupportSessions(base: string, token: string): UseSupportSessions {
  const api = normalizeBase(base)
  const [sessions, setSessions] = useState<SupportSessionRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const namesRef = useRef<Record<string, string>>({})
  const linksRef = useRef<Record<string, string>>({})

  const refresh = useCallback(async () => {
    try {
      const r = await fetch(`${api}/api/support/list`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!r.ok) {
        setError('Could not load sessions')
        return
      }
      const rows = (await r.json()) as Array<Record<string, unknown>>
      setSessions(
        rows.map((x) => {
          const id = String(x.id)
          return {
            id,
            code: String(x.code),
            link: linksRef.current[id] || `${api}/join/${String(x.code)}`,
            name: namesRef.current[id] || (x.label as string) || String(x.code),
            status: String(x.status),
            machine_id: (x.machine_id as string) ?? null,
            joined_at: (x.joined_at as string) ?? null
          }
        })
      )
      setError(null)
    } catch {
      setError('Could not reach the server')
    } finally {
      setLoading(false)
    }
  }, [api, token])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 4000)
    return () => clearInterval(t)
  }, [refresh])

  const create = useCallback(async () => {
    try {
      const r = await fetch(`${api}/api/support/create`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!r.ok) {
        setError('Could not create a session')
        return null
      }
      const d = await r.json()
      const row: SupportSessionRow = {
        id: d.session_id,
        code: d.code,
        link: d.link,
        name: d.code,
        status: d.status,
        machine_id: null,
        joined_at: null
      }
      // The create response carries the real shareable link; keep it, because
      // /list doesn't return one.
      linksRef.current[row.id] = d.link
      setSessions((p) => [row, ...p.filter((s) => s.id !== row.id)])
      setError(null)
      return row
    } catch {
      setError('Could not reach the server')
      return null
    }
  }, [api, token])

  const end = useCallback(
    async (id: string) => {
      try {
        await fetch(`${api}/api/support/${id}/end`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` }
        })
      } catch {
        /* the poll will resync */
      }
      setSessions((p) => p.filter((s) => s.id !== id))
    },
    [api, token]
  )

  const rename = useCallback((id: string, name: string) => {
    namesRef.current[id] = name
    setSessions((p) => p.map((s) => (s.id === id ? { ...s, name } : s)))
  }, [])

  return { sessions, loading, error, refresh, create, end, rename }
}
