import { useState } from 'react'
import { Check, Copy, X } from 'lucide-react'
import { enrollMachine } from '../api'
import type { MachineEnrolled } from '../types'

interface Props {
  base: string
  token: string
  serverUrl: string
  onClose: () => void
  onEnrolled: () => void
}

export function AddMachineDialog({ base, token, serverUrl, onClose, onEnrolled }: Props) {
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<MachineEnrolled | null>(null)
  const [copied, setCopied] = useState<string | null>(null)

  const submit = async () => {
    if (!name.trim()) return
    setBusy(true)
    setError(null)
    try {
      const m = await enrollMachine(base, token, name.trim())
      setResult(m)
      onEnrolled()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Enrollment failed')
    } finally {
      setBusy(false)
    }
  }

  const wsBase = serverUrl.replace(/^http/i, (m) => (m.toLowerCase() === 'https' ? 'wss' : 'ws'))
  const configSnippet =
    result &&
    JSON.stringify(
      {
        server_url: wsBase,
        token: result.agent_token,
        show_tray_icon: true,
        notify_on_session: true,
        allow_remote_input: true
      },
      null,
      2
    )

  const copy = (text: string, key: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(key)
      setTimeout(() => setCopied(null), 1500)
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/70 p-4">
      <div className="card w-full max-w-lg p-5 shadow-glow">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-fg">
            {result ? 'Machine enrolled' : 'Add machine'}
          </h2>
          <button onClick={onClose} className="text-faint hover:text-fg" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        {!result ? (
          <>
            <label className="label" htmlFor="machine-name">
              Machine name
            </label>
            <input
              id="machine-name"
              autoFocus
              className="field"
              placeholder="e.g. Front desk PC"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submit()}
            />
            {error && <p className="mt-2 text-sm text-warn">{error}</p>}
            <div className="mt-5 flex justify-end gap-2">
              <button className="btn-ghost" onClick={onClose}>
                Cancel
              </button>
              <button className="btn-primary" onClick={submit} disabled={busy || !name.trim()}>
                {busy ? 'Enrolling…' : 'Add machine'}
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="text-sm text-dim">
              This token is shown once. Put it in the agent’s{' '}
              <span className="font-mono text-fg">config.json</span> on the endpoint.
            </p>

            <div className="mt-4">
              <div className="label flex items-center justify-between">
                <span>Agent token</span>
                <button
                  className="inline-flex items-center gap-1 text-signal hover:underline"
                  onClick={() => copy(result.agent_token, 'token')}
                >
                  {copied === 'token' ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                  copy
                </button>
              </div>
              <code className="block break-all rounded-md border border-line bg-ink/60 p-2 font-mono text-xs text-fg">
                {result.agent_token}
              </code>
            </div>

            <div className="mt-4">
              <div className="label flex items-center justify-between">
                <span>config.json</span>
                <button
                  className="inline-flex items-center gap-1 text-signal hover:underline"
                  onClick={() => configSnippet && copy(configSnippet, 'config')}
                >
                  {copied === 'config' ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                  copy
                </button>
              </div>
              <pre className="max-h-48 overflow-auto rounded-md border border-line bg-ink/60 p-3 font-mono text-xs text-dim">
                {configSnippet}
              </pre>
            </div>

            <div className="mt-5 flex justify-end">
              <button className="btn-primary" onClick={onClose}>
                Done
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
