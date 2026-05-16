import { useEffect } from 'react'

export interface ToastState {
  message: string
  tone: 'success' | 'error'
}

export function Toast({
  toast,
  onClear,
}: {
  toast: ToastState | null
  onClear: () => void
}) {
  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(onClear, 2600)
    return () => window.clearTimeout(timer)
  }, [toast, onClear])

  if (!toast) return null

  return (
    <div className="pointer-events-none fixed right-6 top-6 z-50">
      <div
        className={[
          'rounded-2xl border px-4 py-3 text-sm font-bold shadow-[0_20px_60px_rgba(15,23,42,0.18)]',
          toast.tone === 'success'
            ? 'border-toptrader-brand/20 bg-toptrader-brand/10 text-toptrader-brand'
            : 'border-toptrader-rose/30 bg-toptrader-rose/10 text-toptrader-rose',
        ].join(' ')}
      >
        {toast.message}
      </div>
    </div>
  )
}
