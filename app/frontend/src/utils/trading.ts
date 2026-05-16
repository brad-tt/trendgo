import type { DailyRecord } from '../types'

/**
 * 根据交易记录判断实际使用的 trading mode。
 * US 市场或 US stock options 标的时，统一返回 'us_stock_options'。
 */
export function effectiveTradingMode(day: DailyRecord | null | undefined): string {
  if (!day) {
    return 'us_stock_options'
  }
  if (day.base.market === 'US' || day.base.primaryInstrument === 'US stock options') {
    return 'us_stock_options'
  }
  return day.workbench.tradingMode
}
