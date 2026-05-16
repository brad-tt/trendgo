import type { Trade } from '../../types'

export type TradeEditorMode = 'close' | 'create' | 'edit'

export interface TradeWritePayload {
  abcGrade: string
  abnormalScenario: string
  autoRuleEvent?: boolean
  certificateFilterPassed: boolean
  certificateSide: string
  confirmationOk: boolean
  direction: string
  directionClear: boolean
  entryPrice: number
  entryReason: string
  exitPrice?: number
  exitTime?: string
  followedPlan: boolean
  instrumentCode: string
  instrumentType: string
  locationOk: boolean
  pnlAmount?: number
  positionSize: string
  postTradeEmotion?: string
  result?: 'breakeven' | 'loss' | 'win'
  riskClear: boolean
  ruleViolation: boolean
  sessionWindow: string
  setupType: string
  stopLoss: number
  targetPrice?: number
  tradeTime: string
  underlying: string
}

export type TradeFormState = {
  abcGrade: string
  abnormalScenario: string
  certificateFilterPassed: boolean
  certificateSide: string
  confirmationOk: boolean
  direction: string
  directionClear: boolean
  entryPrice: string
  entryReason: string
  exitPrice: string
  exitTime: string
  followedPlan: boolean
  instrumentCode: string
  instrumentType: string
  locationOk: boolean
  positionSize: string
  riskClear: boolean
  ruleViolation: boolean
  sessionWindow: string
  setupType: string
  stopLoss: string
  targetPrice: string
  tradeTime: string
  underlying: string
}

export function normalizeClockValue(value: string): string | null {
  const text = value.trim()
  if (!text) {
    return ''
  }
  if (/^\d{1,2}:\d{2}(:\d{2})?$/.test(text)) {
    const [hoursText, minutesText] = text.split(':')
    const hours = Number(hoursText)
    const minutes = Number(minutesText)
    if (hours >= 0 && hours <= 23 && minutes >= 0 && minutes <= 59) {
      return `${hours.toString().padStart(2, '0')}:${minutesText}`
    }
    return null
  }
  if (/^\d{3,4}$/.test(text)) {
    const hours = Number(text.slice(0, -2))
    const minutes = Number(text.slice(-2))
    if (hours >= 0 && hours <= 23 && minutes >= 0 && minutes <= 59) {
      return `${hours.toString().padStart(2, '0')}:${text.slice(-2)}`
    }
  }
  return null
}

export function parseOptionalNumber(value: string): number | null {
  const text = value.trim().replace(/,/g, '')
  if (!text) {
    return null
  }
  const parsed = Number(text)
  return Number.isFinite(parsed) ? parsed : null
}

function roundTradeValue(value: number): number {
  return Math.round(value * 10000) / 10000
}

export function computeTradeOutcome(form: TradeFormState) {
  const entryPrice = parseOptionalNumber(form.entryPrice)
  const exitPrice = parseOptionalNumber(form.exitPrice)
  const positionSize = parseOptionalNumber(form.positionSize)

  if (entryPrice === null || exitPrice === null) {
    return {
      pnlAmount: null,
      positionSize,
      result: null as 'breakeven' | 'loss' | 'win' | null,
      signedMove: null as number | null,
    }
  }

  const signedMove = exitPrice - entryPrice
  const result: 'win' | 'loss' | 'breakeven' =
    signedMove > 1e-9 ? 'win' : signedMove < -1e-9 ? 'loss' : 'breakeven'

  return {
    pnlAmount: positionSize === null ? null : roundTradeValue(signedMove * positionSize),
    positionSize,
    result,
    signedMove: roundTradeValue(signedMove),
  }
}

export function getTradeErrors(form: TradeFormState, mode: TradeEditorMode = 'edit') {
  const errors: Partial<Record<keyof TradeFormState, string>> = {}
  const tradeTime = normalizeClockValue(form.tradeTime)
  const exitTime = normalizeClockValue(form.exitTime)
  const hasExitPrice = form.exitPrice.trim() !== ''
  const entryPrice = parseOptionalNumber(form.entryPrice)
  const exitPrice = parseOptionalNumber(form.exitPrice)
  const positionSize = parseOptionalNumber(form.positionSize)
  const stopLoss = parseOptionalNumber(form.stopLoss)

  if (tradeTime === null) {
    errors.tradeTime = '开仓时间可留空；填写时请使用 HH:MM。'
  }
  if (exitTime === null) {
    errors.exitTime = '平仓时间可留空；填写时请使用 HH:MM。'
  }
  if (!form.abcGrade) {
    errors.abcGrade = '请选择机会等级。'
  }
  if (!form.instrumentCode.trim()) {
    errors.instrumentCode = '请填写标的代码。'
  }
  if (entryPrice === null) {
    errors.entryPrice = '请填写有效的入场价。'
  }
  if (stopLoss === null) {
    errors.stopLoss = '请填写有效的止损价。'
  }
  if (positionSize === null) {
    errors.positionSize = '请填写数字仓位。'
  }
  if (!form.entryReason.trim()) {
    errors.entryReason = '请填写入场逻辑。'
  }
  if (mode === 'close') {
    if (!form.exitTime.trim()) {
      errors.exitTime = '请填写平仓时间。'
    }
    if (exitPrice === null) {
      errors.exitPrice = '请填写有效的平仓价格。'
    }
  }
  if (hasExitPrice && positionSize === null) {
    errors.positionSize = '已填写平仓价时，仓位必须是数字，系统才能自动计算盈亏。'
  }

  return errors
}

export function createTradeForm(mode: string, trade?: Trade): TradeFormState {
  if (!trade) {
    return {
      abcGrade: '',
      abnormalScenario: 'none',
      certificateFilterPassed: true,
      certificateSide: mode === 'us_stock_options' ? 'call' : 'bull',
      confirmationOk: true,
      direction: 'long',
      directionClear: true,
      entryPrice: '',
      entryReason: '',
      exitPrice: '',
      exitTime: '',
      followedPlan: true,
      instrumentCode: '',
      instrumentType: mode === 'us_stock_options' ? 'stock_option' : 'bull_bear_certificate',
      locationOk: true,
      positionSize: '',
      riskClear: true,
      ruleViolation: false,
      sessionWindow: 'mid_session',
      setupType: mode === 'us_stock_options' ? 'orb_continuation' : 'opening_breakout',
      stopLoss: '',
      targetPrice: '',
      tradeTime: '',
      underlying: mode === 'us_stock_options' ? 'TSLA' : 'HSI',
    }
  }

  return {
    abcGrade: trade.abcGrade,
    abnormalScenario: trade.abnormalScenario || 'none',
    certificateFilterPassed: trade.certificateFilterPassed !== false,
    certificateSide: trade.certificateSide || (mode === 'us_stock_options' ? 'call' : 'bull'),
    confirmationOk: trade.confirmationOk !== false,
    direction: trade.direction,
    directionClear: trade.directionClear !== false,
    entryPrice: trade.entryPrice?.toString() ?? '',
    entryReason: trade.entryReason,
    exitPrice: trade.exitPrice?.toString() ?? '',
    exitTime: normalizeClockValue(trade.exitTime) ?? '',
    followedPlan: trade.followedPlan,
    instrumentCode: trade.instrumentCode,
    instrumentType: trade.instrumentType,
    locationOk: trade.locationOk !== false,
    positionSize: trade.positionSize,
    riskClear: trade.riskClear !== false,
    ruleViolation: trade.ruleViolation,
    sessionWindow: trade.sessionWindow,
    setupType: trade.setupType,
    stopLoss: trade.stopLoss?.toString() ?? '',
    targetPrice: trade.targetPrice?.toString() ?? '',
    tradeTime: normalizeClockValue(trade.tradeTime) ?? '',
    underlying: trade.underlying,
  }
}
