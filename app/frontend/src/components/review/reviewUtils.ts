import type { Trade } from '../../types'

export const fieldClassName = 'tt-input'

export function buildFieldClassName(hasError = false) {
  return [fieldClassName, hasError ? 'tt-input-error bg-toptrader-rose/5' : ''].join(' ')
}

export function formatTradeTimeRange(trade: Trade) {
  const entry = trade.tradeTime || '未填开仓'
  const exit = trade.exitTime || '未填平仓'
  return `${entry} → ${exit}`
}

export function pnlToneClass(value: number | null) {
  if (value === null) return 'text-toptrader-accent'
  if (value > 0) return 'text-emerald-500'
  if (value < 0) return 'text-toptrader-rose'
  return 'text-toptrader-muted'
}
