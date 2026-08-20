import { useState } from 'react'
import { Radio } from 'lucide-react'
import { useAuth } from '../auth'

// Used only by the desktop build, which loads from file:// and so has no
// origin to infer the server from. The web build ignores this.
const DESKTOP_FALLBACK_SERVER = 'https://rmm.remotedesk247.com'

/**
 * Where the API lives. Served over http(s) — the web console — the API is on
 * the same origin, because nginx proxies /api to the FastAPI app. That's why
 * there's no Server field to fill in any more.
 */
function resolveServer(): string {
  if (typeof window !== 'undefined' && window.location.protocol.startsWith('http')) {
    return window.location.origin
  }
  return DESKTOP_FALLBACK_SERVER
}

export function Login() {
  const { signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      await signIn(resolveServer(), email, password)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sign in failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-signal/15 text-signal">
            <Radio className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-fg">RMM Console</h1>
            <p className="text-sm text-dim">Sign in to your monitoring server</p>
          </div>
        </div>

        <div className="card p-5">
          <label className="label" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            className="field mb-4"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            placeholder="you@example.com"
          />

          <label className="label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            className="field"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            placeholder="••••••••"
          />

          {error && <p className="mt-3 text-sm text-warn">{error}</p>}

          <button
            className="btn-primary mt-5 w-full"
            onClick={submit}
            disabled={busy || !email || !password}
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </div>

        <p className="mt-4 text-center text-xs text-faint">
          The first account registered on a server becomes the admin.
        </p>
      </div>
    </div>
  )
}
