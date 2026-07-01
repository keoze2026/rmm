import { useCallback, useEffect, useRef, useState } from 'react'
import { Folder, File as FileIcon, ArrowUp, Download, Upload, RefreshCw } from 'lucide-react'

type SendCommand = (action: string, payload: Record<string, unknown>) => void
type Subscribe = (fn: (msg: Record<string, unknown>) => void) => () => void

interface Props {
  sendCommand: SendCommand
  subscribe: Subscribe
}

interface Entry {
  name: string
  is_dir: boolean
  size: number
  mtime: number
}

const CHUNK = 192 * 1024 // bytes per upload chunk (base64-expands to ~256 KB)

function joinPath(dir: string, name: string): string {
  if (dir.endsWith('/') || dir.endsWith('\\')) return dir + name
  const sep = dir.includes('\\') && !dir.includes('/') ? '\\' : '/'
  return dir + sep + name
}

function humanSize(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(1)} GB`
}

function b64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

function bytesToB64(bytes: Uint8Array): string {
  let bin = ''
  const step = 0x8000
  for (let i = 0; i < bytes.length; i += step) {
    bin += String.fromCharCode(...bytes.subarray(i, i + step))
  }
  return btoa(bin)
}

export function FilesPanel({ sendCommand, subscribe }: Props) {
  const [cwd, setCwd] = useState<string>('')
  const [parent, setParent] = useState<string | null>(null)
  const [entries, setEntries] = useState<Entry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  // Accumulate download chunks per transfer.
  const downloads = useRef<Map<string, { name: string; parts: Uint8Array[] }>>(new Map())

  const list = useCallback(
    (path: string | null) => {
      setError(null)
      sendCommand('fs_list', { path })
    },
    [sendCommand]
  )

  useEffect(() => {
    list(null) // null => agent defaults to the user's home
  }, [list])

  useEffect(() => {
    const unsub = subscribe((msg) => {
      if (msg.type === 'agent_event') {
        if (msg.event === 'fs_list') {
          if (msg.ok) {
            setCwd(String(msg.path))
            setParent((msg.parent as string) ?? null)
            setEntries((msg.entries as Entry[]) ?? [])
            setError(null)
          } else {
            setError(String(msg.error || 'Could not open folder'))
          }
        } else if (msg.event === 'fs_error') {
          setError(String(msg.reason || 'File operation failed'))
          setBusy(false)
        } else if (msg.event === 'fs_write_done') {
          setBusy(false)
          list(cwd) // refresh after an upload
        } else if (msg.event === 'error' && msg.reason === 'no_active_session') {
          setError('Session is not active.')
        }
      } else if (msg.type === 'file_chunk') {
        const id = String(msg.transfer_id)
        const rec = downloads.current.get(id)
        if (!rec) return
        if (msg.data) rec.parts.push(b64ToBytes(msg.data as string))
        if (msg.eof) {
          const blob = new Blob(rec.parts as BlobPart[])
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = rec.name
          a.click()
          URL.revokeObjectURL(url)
          downloads.current.delete(id)
        }
      }
    })
    return unsub
  }, [subscribe, cwd, list])

  const openEntry = (e: Entry) => {
    if (e.is_dir) list(joinPath(cwd, e.name))
  }

  const download = (e: Entry) => {
    const id = `${Date.now()}-${e.name}`
    downloads.current.set(id, { name: e.name, parts: [] })
    sendCommand('fs_read', { transfer_id: id, path: joinPath(cwd, e.name) })
  }

  const onUpload = async (ev: React.ChangeEvent<HTMLInputElement>) => {
    const file = ev.target.files?.[0]
    ev.target.value = ''
    if (!file) return
    setBusy(true)
    setError(null)
    const buf = new Uint8Array(await file.arrayBuffer())
    const dest = joinPath(cwd, file.name)
    if (buf.length === 0) {
      sendCommand('fs_write', { path: dest, data: '', first: true, last: true })
      return
    }
    const total = Math.ceil(buf.length / CHUNK)
    for (let i = 0; i < total; i++) {
      const slice = buf.subarray(i * CHUNK, (i + 1) * CHUNK)
      sendCommand('fs_write', {
        path: dest,
        data: bytesToB64(slice),
        first: i === 0,
        last: i === total - 1
      })
    }
  }

  return (
    <div className="flex h-full flex-col bg-surface">
      <div className="flex items-center gap-2 border-b border-line px-3 py-2">
        <button
          className="btn-ghost px-2 py-1"
          onClick={() => parent && list(parent)}
          disabled={!parent}
          title="Up"
        >
          <ArrowUp className="h-4 w-4" />
        </button>
        <button className="btn-ghost px-2 py-1" onClick={() => list(cwd)} title="Refresh">
          <RefreshCw className="h-4 w-4" />
        </button>
        <span className="flex-1 truncate font-mono text-xs text-dim" title={cwd}>
          {cwd || '…'}
        </span>
        <button
          className="btn-primary px-2 py-1"
          onClick={() => fileInputRef.current?.click()}
          disabled={busy || !cwd}
          title="Upload a file to this folder"
        >
          <Upload className="h-4 w-4" />
          {busy ? 'Uploading…' : 'Upload'}
        </button>
        <input ref={fileInputRef} type="file" className="hidden" onChange={onUpload} />
      </div>

      {error && <div className="px-3 py-2 text-xs text-warn">{error}</div>}

      <div className="flex-1 overflow-auto">
        <table className="w-full text-left text-sm">
          <tbody>
            {entries.map((e) => (
              <tr
                key={e.name}
                className="border-b border-line/40 hover:bg-raised/60"
                onDoubleClick={() => openEntry(e)}
              >
                <td className="px-3 py-1.5">
                  <button
                    className="flex items-center gap-2 text-left"
                    onClick={() => openEntry(e)}
                    disabled={!e.is_dir}
                  >
                    {e.is_dir ? (
                      <Folder className="h-4 w-4 text-signal" />
                    ) : (
                      <FileIcon className="h-4 w-4 text-faint" />
                    )}
                    <span className={e.is_dir ? 'text-fg' : 'text-dim'}>{e.name}</span>
                  </button>
                </td>
                <td className="px-3 py-1.5 text-right font-mono text-xs text-faint">
                  {e.is_dir ? '' : humanSize(e.size)}
                </td>
                <td className="px-3 py-1.5 text-right">
                  {!e.is_dir && (
                    <button
                      className="text-signal hover:underline"
                      onClick={() => download(e)}
                      title="Download"
                    >
                      <Download className="h-4 w-4" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {entries.length === 0 && !error && (
              <tr>
                <td className="px-3 py-6 text-center text-xs text-faint">Empty folder</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}