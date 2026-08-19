import { Plus } from 'lucide-react'

interface Props {
  count: number
  onCreate: () => void
  creating: boolean
}

/**
 * Second column: section heading, the Create action, and the list selector
 * with its live count.
 */
export function SectionPanel({ count, onCreate, creating }: Props) {
  return (
    <aside className="flex w-[300px] flex-shrink-0 flex-col border-r border-line bg-surface">
      <div className="flex h-[68px] items-center px-8">
        <h1 className="text-[26px] font-normal leading-none text-fg">Support</h1>
      </div>

      <p className="px-8 pb-5 text-[13px] leading-relaxed text-dim">
        Provide on-demand support for any device on the internet.
      </p>

      <div className="px-8">
        <button
          onClick={onCreate}
          disabled={creating}
          className="flex w-full items-center justify-center gap-1.5 rounded bg-signal py-2.5 text-[15px] font-medium text-white transition-colors hover:bg-signalHover disabled:opacity-60"
        >
          {creating ? 'Creating…' : 'Create'}
          {!creating && <Plus className="h-4 w-4" strokeWidth={2.5} />}
        </button>
      </div>

      <div className="mt-6 px-8">
        <div className="flex items-center justify-between rounded bg-ink px-4 py-2.5 text-[14px] text-fg">
          <span>My Sessions</span>
          <span className="text-dim">{count}</span>
        </div>
      </div>
    </aside>
  )
}
