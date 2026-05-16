export { Field as TradeField } from '../ui/Field'
export { FieldError } from '../ui/FieldError'
export { ToggleRow } from '../ui/ToggleRow'
export { SummaryCard } from '../ui/SummaryCard'
export { ReadonlyValue as ReadonlyTradeValue } from '../ui/ReadonlyValue'
export { Badge as MetaBadge } from '../ui/Badge'
export { MetaRow } from '../ui/MetaRow'

import type { ReactNode } from 'react'

export function ReviewField({
  children,
  label,
}: {
  children: ReactNode
  label: string
}) {
  return (
    <label className="grid gap-2 text-sm text-toptrader-muted">
      <span className="font-medium text-toptrader-ink">{label}</span>
      {children}
    </label>
  )
}
