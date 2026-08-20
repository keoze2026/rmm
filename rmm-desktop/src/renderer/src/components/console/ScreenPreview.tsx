import { useCallback, useRef } from 'react'
import { Maximize2 } from 'lucide-react'
import { useRemoteSession } from '../../useRemoteSession'

interface Props {
  base: string
  token: string
  machineId: string
  onOpen: () => void
}

/**
 * Small live view of the guest's screen inside the detail column.
 *
 * Frames arrive on a real session, so the person at the other end gets their
 * notification and the tray turns blue — same consent surface as the full
 * viewer. Clicking opens the full-size viewer.
 */
export function ScreenPreview({ base, token, machineId, onOpen }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null)

  const drawFrame = useCallback((bitmap: ImageBitmap) => {
    const canvas = canvasRef.current
    if (!canvas) {
      bitmap.close()
      return
    }
    if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
      canvas.width = bitmap.width
      canvas.height = bitmap.height
    }
    let ctx = ctxRef.current
    if (!ctx) {
      ctx = canvas.getContext('2d')
      ctxRef.current = ctx
    }
    ctx?.drawImage(bitmap, 0, 0)
    bitmap.close()
  }, [])

  const { status, error } = useRemoteSession(base, token, machineId, { onFrame: drawFrame })

  return (
    <div className="mt-6">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[13px] text-fg">Guest screen</span>
        <span className="text-[12px] text-dim">
          {status === 'live' ? 'Live' : status === 'error' ? 'Unavailable' : 'Connecting…'}
        </span>
      </div>

      <button
        onClick={onOpen}
        title="Open full screen"
        className="group relative block w-full overflow-hidden rounded border border-line bg-[#0B0F14]"
        style={{ aspectRatio: '16 / 10' }}
      >
        <canvas ref={canvasRef} className="h-full w-full object-contain" />

        {status !== 'live' && (
          <span className="absolute inset-0 flex items-center justify-center text-[12px] text-dim">
            {error || 'Waiting for the first frame…'}
          </span>
        )}

        <span className="absolute inset-0 flex items-center justify-center bg-fg/0 opacity-0 transition-opacity group-hover:bg-fg/40 group-hover:opacity-100">
          <span className="flex items-center gap-1.5 rounded bg-surface px-3 py-1.5 text-[13px] font-medium text-fg">
            <Maximize2 className="h-3.5 w-3.5" />
            Open full screen
          </span>
        </span>
      </button>
    </div>
  )
}
