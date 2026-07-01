interface StatusDotProps {
  online: boolean
}

export function StatusDot({ online }: StatusDotProps) {
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${online ? 'dot-online' : 'dot-offline'}`}
      aria-label={online ? 'online' : 'offline'}
    />
  )
}

export function relativeTime(iso: string | null): string {
  if (!iso) return 'never'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return 'unknown'
  const secs = Math.max(0, Math.floor((Date.now() - then) / 1000))
  if (secs < 10) return 'just now'
  if (secs < 60) return `${secs}s ago`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}
