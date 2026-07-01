import { useAuth } from './auth'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'

export default function App() {
  const { session, ready } = useAuth()

  if (!ready) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-dim">Loading…</div>
    )
  }

  return session ? <Dashboard /> : <Login />
}
