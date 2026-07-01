import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { getMe, login as apiLogin, normalizeBase } from './api'
import type { User } from './types'

interface Session {
  base: string
  token: string
  user: User
}

interface AuthContextValue {
  session: Session | null
  ready: boolean
  signIn: (base: string, email: string, password: string) => Promise<void>
  signOut: () => void
}

const STORAGE_KEY = 'rmm.session'
const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [ready, setReady] = useState(false)

  // Restore a saved session on launch; verify the token still works.
  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      setReady(true)
      return
    }
    try {
      const saved = JSON.parse(raw) as { base: string; token: string }
      getMe(saved.base, saved.token)
        .then((user) => setSession({ base: normalizeBase(saved.base), token: saved.token, user }))
        .catch(() => localStorage.removeItem(STORAGE_KEY))
        .finally(() => setReady(true))
    } catch {
      localStorage.removeItem(STORAGE_KEY)
      setReady(true)
    }
  }, [])

  const signIn = useCallback(async (base: string, email: string, password: string) => {
    const cleanBase = normalizeBase(base)
    const token = await apiLogin(cleanBase, email, password)
    const user = await getMe(cleanBase, token)
    const next = { base: cleanBase, token, user }
    setSession(next)
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ base: cleanBase, token }))
  }, [])

  const signOut = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY)
    setSession(null)
  }, [])

  const value = useMemo(
    () => ({ session, ready, signIn, signOut }),
    [session, ready, signIn, signOut]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
