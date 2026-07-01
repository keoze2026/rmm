import { useState } from 'react'
import { Radio } from 'lucide-react'
import { useAuth } from '../auth'

const DEFAULT_SERVER = 'http://localhost:8765'

export function Login() {
  const { signIn } = useAuth()
  const [base, setBase] = useState(DEFAULT_SERVER)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      await signIn(base, email, password)
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
          <label className="label" htmlFor="server">
            Server
          </label>
          <input
            id="server"
            className="field mb-4 font-mono text-xs"
            value={base}
            onChange={(e) => setBase(e.target.value)}
            placeholder="http://localhost:8765"
          />

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
            disabled={busy || !email || !password || !base}
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
