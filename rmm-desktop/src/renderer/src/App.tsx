import { useAuth } from './auth'
import { Login } from './pages/Login'
import { Console } from './pages/Console'

export default function App() {
  const { session, ready } = useAuth()

  if (!ready) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-dim">Loading…</div>
    )
  }

  return session ? <Console /> : <Login />
}
