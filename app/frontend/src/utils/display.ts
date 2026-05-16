const DISPLAY_LABELS: Record<string, string> = {
  hsi_bull_bear_certificate: '恒指牛熊证',
  us_stock_options: '美股期权',
  'HSI bull/bear certificate': '恒指牛熊证',
  'US stock options': '美股期权',
  HK: '港股',
  US: '美股',
  undecided: '未定',
  long: '做多',
  short: '做空',
  observe: '观察',
  unset: '未设',
  stable: '稳定',
  impatient: '偏急',
  defiant: '顶撞',
  tired: '疲惫',
  unfit: '不适合交易',
  opening_breakout: '开盘突破',
  pullback_reclaim: '回踩确认',
  clear_observe: '观察',
  orb_continuation: '开盘区间突破延续',
  vwap_reclaim: 'VWAP 收复',
  trend_pullback: '趋势回踩',
  support_reversal: '支撑反转',
  failed_breakdown: '跌破失败反转',
  breakout_if_confirmed: '确认突破',
  pullback_only: '回踩优先',
  observe_first: '先观察',
  clear_no_trade: '不清晰不做',
  wait_first_15m: '先等 15 分钟',
  trend_continuation: '趋势延续',
  avoid_event_risk: '避开事件风险',
  opening_30m: '开盘时段',
  mid_session: '盘中时段',
  late_session: '尾段时段',
  call: 'Call',
  put: 'Put',
  bull: '牛证',
  bear: '熊证',
  stock_option: '股票期权',
  bull_bear_certificate: '牛熊证',
  win: '盈利',
  loss: '亏损',
  breakeven: '持平',
  rule_violation: '规则违规',
  emotion_trigger: '情绪触发',
  forced_pause: '强制暂停',
  forced_stop: '强制停手',
  overtrade_signal: '过度交易信号',
  warning: '预警',
  stop: '暂停',
  critical: '严重',
  none: '无',
}

export function displayValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') {
    return '--'
  }
  const text = String(value)
  return DISPLAY_LABELS[text] ?? text
}

export function formatTradeDate(value: string | null | undefined): string {
  if (!value) {
    return '--'
  }
  const match = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(value)
  if (!match) {
    return value
  }
  const [, year, month, day] = match
  return `${year}年${Number(month)}月${Number(day)}日`
}
