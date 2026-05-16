import type { Trade } from '../types'

export let USD_HKD_RATE = 7.8

export function setUsdHkdRate(rate: number) {
  USD_HKD_RATE = rate
}

export function tradeCurrency(trade: Pick<Trade, 'certificateSide' | 'instrumentType'>): 'HKD' | 'USD' {
  if (trade.instrumentType === 'stock_option' || trade.certificateSide === 'call' || trade.certificateSide === 'put') {
    return 'USD'
  }
  return 'HKD'
}

export function toHkd(value: number | null | undefined, currency: 'HKD' | 'USD') {
  if (value === null || value === undefined) {
    return null
  }
  return currency === 'USD' ? roundMoney(value * USD_HKD_RATE) : roundMoney(value)
}

export function tradePnlHkd(trade: Trade) {
  return toHkd(trade.pnlAmount, trade.currency ?? tradeCurrency(trade))
}

export function sumTradesPnlHkd(trades: Trade[]) {
  return roundMoney(trades.reduce((sum, trade) => sum + (tradePnlHkd(trade) ?? 0), 0))
}

export function winRateText(trades: Trade[]) {
  if (!trades.length) {
    return '--'
  }
  const wins = trades.filter((trade) => trade.result === 'win').length
  return `${formatNumber((wins / trades.length) * 100)}%`
}

export function formatHkdSummaryAmount(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '--'
  }
  return formatNumber(value)
}

export function formatTradePnl(trade: Trade) {
  if (trade.pnlAmount === null || trade.pnlAmount === undefined) {
    return {
      primary: '--',
      secondary: '',
    }
  }
  const currency = trade.currency ?? tradeCurrency(trade)
  const primary = `${currency === 'USD' ? 'US$' : 'HK$'} ${formatNumber(trade.pnlAmount)}`
  return {
    primary,
    secondary: '',
  }
}

export function formatNumber(value: number) {
  if (Number.isInteger(value)) {
    return value.toString()
  }
  return value.toFixed(2).replace(/\.?0+$/, '')
}

function roundMoney(value: number) {
  return Math.round(value * 100) / 100
}
