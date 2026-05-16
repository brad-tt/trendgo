import type { ReactNode } from 'react'

export function Field({
  children,
  className = '',
  label,
}: {
  children: ReactNode
  className?: string
  label: string
}) {
  return (
    <label className={['grid gap-1.5 text-[12px] text-toptrader-muted', className].join(' ')}>
      <span className="font-medium text-toptrader-ink">{label}</span>
      {children}
    </label>
  )
}
