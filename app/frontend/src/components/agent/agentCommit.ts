import type { AgentWorkflowResult, DailyRecord } from '../../types'

export interface AgentCommitResponse {
  committed: boolean
  message: string
  missingFields?: string[]
  missingLabels?: string[]
  feedbackMessages?: string[]
  day?: DailyRecord
  autoEventId?: string
  targetTradeId?: string
  ruleHits?: AgentRuleHit[]
  knowledgeRoutes?: AgentKnowledgeRoute[]
}

export interface AgentRuleHit {
  ruleId?: string
  severity?: string
  message?: string
}

export interface AgentKnowledgeRoute {
  routeId?: string
  firstAction?: string
}

export interface AgentCommitPayload {
  intent: string
  tradeDate: string
  market: 'HK' | 'US'
  rawNote: string
  fields: Record<string, unknown>
  agentNote?: string
}

export interface PendingAgentPayload {
  intent: string
  tradeDate: string
  market: 'HK' | 'US'
  rawNotes: string[]
  fields: Record<string, unknown>
  missingFields: string[]
  missingLabels: string[]
  explicitConfirmRequired: boolean
  conflictMessages: string[]
}

const SETUP_ALIASES: Array<[string[], string]> = [
  [['突破回踩', '趋势回踩', '回踩守住', '回踩确认', '回踩站回', '趋势回调'], 'trend_pullback'],
  [['开盘突破', '突破确认', '确认突破'], 'opening_breakout'],
  [['假突破追单', '假突破误追', '追单'], 'false_breakout_chase'],
  [['观察', '先看', '不急'], 'clear_observe'],
  [['VWAP 收复', 'VWAP收复', '站回VWAP'], 'vwap_reclaim'],
  [['支撑反转'], 'support_reversal'],
  [['跌破失败', '假跌破'], 'failed_breakdown'],
]

const VALID_SETUPS = new Set([
  'opening_breakout',
  'pullback_reclaim',
  'clear_observe',
  'false_breakout_chase',
  'reverse_after_stop',
  'emotional_trade',
  'revenge_trade',
  'itchy_hand_trade',
  'profit_giveback',
  'recovery_after_losing_streak',
  'orb_continuation',
  'vwap_reclaim',
  'trend_pullback',
  'support_reversal',
  'failed_breakdown',
  'iv_chase',
  'other',
])

const VALID_PRE_TRADE_EMOTIONS = new Set(['stable', 'rushed', 'defiant', 'fomo', 'recover_loss'])
const VALID_EMOTION_STATES = new Set(['stable', 'anxious', 'revenge', 'impulsive'])
const VALID_POST_TRADE_EMOTIONS = new Set(['unset', 'stable', 'satisfied', 'regret', 'rushed', 'defiant'])

const FIELD_ALIASES: Record<string, string> = {
  trade_time: 'tradeTime',
  session_window: 'sessionWindow',
  certificate_side: 'certificateSide',
  instrument_code: 'instrumentCode',
  setup_type: 'setupType',
  abc_grade: 'abcGrade',
  direction_clear: 'directionClear',
  location_ok: 'locationOk',
  confirmation_ok: 'confirmationOk',
  risk_clear: 'riskClear',
  certificate_filter_passed: 'certificateFilterPassed',
  entry_price: 'entryPrice',
  stop_loss: 'stopLoss',
  position_size: 'positionSize',
  followed_plan: 'followedPlan',
  rule_violation: 'ruleViolation',
  entry_reason: 'entryReason',
  instrument_type: 'instrumentType',
  abnormal_scenario: 'abnormalScenario',
  auto_rule_event: 'autoRuleEvent',
  post_trade_emotion: 'postTradeEmotion',
  setup_score: 'setupScore',
  setup_validated: 'setupValidated',
  target_price: 'targetPrice',
  exit_time: 'exitTime',
  exit_price: 'exitPrice',
  pnl_amount: 'pnlAmount',
  risk_reward_ratio: 'riskRewardRatio',
  exit_reason: 'exitReason',
  emotion_state: 'emotionState',
  pre_trade_emotion: 'preTradeEmotion',
  violation_note: 'violationNote',
  screenshot_note: 'screenshotNote',
  review_note: 'reviewNote',
  trade_id: 'tradeId',
  event_time: 'eventTime',
  event_type: 'eventType',
  trigger_reason: 'triggerReason',
  action_taken: 'actionTaken',
  follow_up_note: 'followUpNote',
  linked_trade_id: 'linkedTradeId',
  best_trade_note: 'bestTradeNote',
  worst_trade_note: 'worstTradeNote',
  execution_issue: 'executionIssue',
  emotion_issue: 'emotionIssue',
  risk_issue: 'riskIssue',
  next_day_one_fix: 'nextDayOneFix',
  market_issue: 'marketIssue',
  setup_issue: 'setupIssue',
  max_loss_trade: 'maxLossTrade',
  win_rate: 'winRate',
}

const CORE_OPEN_MISSING = new Set(['trade_time', 'tradeTime', 'instrument_code', 'instrumentCode', 'entry_price', 'entryPrice', 'position_size', 'positionSize', 'stop_loss', 'stopLoss'])
const QUALITY_OPEN_MISSING = new Set(['setup_type', 'setupType', 'direction', 'certificate_side', 'certificateSide', 'session_window', 'sessionWindow', 'direction_clear', 'directionClear', 'location_ok', 'locationOk', 'confirmation_ok', 'confirmationOk', 'risk_clear', 'riskClear', 'certificate_filter_passed', 'certificateFilterPassed', 'abc_grade', 'abcGrade'])

export function buildCommitPayload(
  result: AgentWorkflowResult,
  options: {
    intent: string
    tradeDate: string
    market: 'HK' | 'US'
    rawNote: string
  },
): AgentCommitPayload {
  const { intent, tradeDate, market, rawNote } = options
  const normalizedFields = normalizeFields((result.proposal || result) as Record<string, unknown>, intent, rawNote)
  return {
    intent,
    tradeDate,
    market,
    rawNote,
    fields: normalizedFields,
    agentNote: 'frontend structured commit from Agent preview',
  }
}

export function buildCommitPayloadFromPending(pending: PendingAgentPayload): AgentCommitPayload {
  return {
    intent: pending.intent,
    tradeDate: pending.tradeDate,
    market: pending.market,
    rawNote: pending.rawNotes.join('\n'),
    fields: pending.fields,
    agentNote: 'frontend pending payload auto commit',
  }
}

export function normalizeFields(raw: Record<string, unknown>, intent: string, rawNote: string): Record<string, unknown> {
  const fields: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(raw)) {
    if (value === '' || value === null || value === undefined) continue
    const canonical = FIELD_ALIASES[key] || key
    fields[canonical] = value
  }

  const note = rawNote.toLowerCase()
  const setup = normalizeSetup(fields.setupType, rawNote)
  if (setup) fields.setupType = setup

  const emotionState = normalizeEmotionState(fields.emotionState, note)
  if (emotionState) fields.emotionState = emotionState

  const preTradeEmotion = normalizePreTradeEmotion(fields.preTradeEmotion, note)
  if (preTradeEmotion) fields.preTradeEmotion = preTradeEmotion

  if (intent === 'close_trade') {
    const postTradeEmotion = normalizePostTradeEmotion(fields.postTradeEmotion, note)
    if (postTradeEmotion) {
      fields.postTradeEmotion = postTradeEmotion
    } else {
      delete fields.postTradeEmotion
    }
  }

  return fields
}

export function buildPendingPayload(
  result: AgentWorkflowResult,
  options: {
    intent: string
    tradeDate: string
    market: 'HK' | 'US'
    rawNote: string
    previous?: PendingAgentPayload | null
  },
): PendingAgentPayload {
  const { intent, tradeDate, market, rawNote, previous } = options
  const incomingFields = normalizeFields((result.proposal || result) as Record<string, unknown>, intent, rawNote)
  const normalizedPrevious = previous && previous.intent === intent ? previous : null
  const { fields, conflicts } = mergeFields(normalizedPrevious?.fields || {}, incomingFields)
  return {
    intent,
    tradeDate,
    market,
    rawNotes: [...(normalizedPrevious?.rawNotes || []), rawNote],
    fields,
    missingFields: result.missingFields || [],
    missingLabels: result.missingLabels || [],
    explicitConfirmRequired: Boolean(normalizedPrevious?.explicitConfirmRequired) || isDiscussionOnly(rawNote) || conflicts.length > 0,
    conflictMessages: [...(normalizedPrevious?.conflictMessages || []), ...conflicts],
  }
}

export function shouldAutoCommitPending(pending: PendingAgentPayload, canWrite: boolean): boolean {
  return canWrite && !pending.explicitConfirmRequired && pending.intent !== 'unknown'
}

export function prioritizeMissingLabels(fields: string[] = [], labels: string[] = []): string[] {
  if (!fields.length) return labels.slice(0, 3)
  const pairs = fields.map((field, index) => ({ field, label: labels[index] || field }))
  const core = pairs.filter((item) => CORE_OPEN_MISSING.has(item.field))
  const quality = pairs.filter((item) => QUALITY_OPEN_MISSING.has(item.field))
  const rest = pairs.filter((item) => !CORE_OPEN_MISSING.has(item.field) && !QUALITY_OPEN_MISSING.has(item.field))
  return [...core, ...quality, ...rest].map((item) => item.label).slice(0, 3)
}

function mergeFields(previous: Record<string, unknown>, incoming: Record<string, unknown>): { fields: Record<string, unknown>; conflicts: string[] } {
  const fields = { ...previous }
  const conflicts: string[] = []
  for (const [key, value] of Object.entries(incoming)) {
    if (value === '' || value === null || value === undefined) continue
    const current = fields[key]
    if (current !== undefined && current !== '' && String(current) !== String(value)) {
      conflicts.push(`${key}: ${String(current)} -> ${String(value)}`)
    }
    fields[key] = value
  }
  return { fields, conflicts }
}

function isDiscussionOnly(rawNote: string): boolean {
  return /(先别写|不要写|只是讨论|等我确认|先不要提交|别提交)/.test(rawNote)
}

export function buildStopWorkflowMessages(day?: DailyRecord, response?: AgentCommitResponse): string[] {
  const events = day?.events || []
  const newestStop = [...events].reverse().find((event) => event.severity === 'stop' || event.severity === 'critical')
  const severeHit = response?.ruleHits?.find((hit) => hit.severity === 'stop' || hit.severity === 'critical' || hit.severity === 'red')
  if (!newestStop && !severeHit) return []
  return [
    '现在停止新开仓。',
    '请先确认暂停交易；如果还有持仓，只处理平仓和风控。',
    '复述这次触发停手的原因，并写下下一步动作。',
  ]
}

export function buildAutoEventMessage(response: AgentCommitResponse): string {
  if (!response.autoEventId) return ''
  return `交易已正式写入；${response.autoEventId} 是自动风险复核提醒，不是否定当前交易。下一笔前需要重新确认方向、位置、确认、风险和工具过滤。`
}

function normalizeSetup(value: unknown, rawNote: string): string {
  const text = String(value || '').trim()
  if (VALID_SETUPS.has(text)) return text
  const haystack = `${text} ${rawNote}`.toLowerCase()
  for (const [aliases, setup] of SETUP_ALIASES) {
    if (aliases.some((alias) => haystack.includes(alias.toLowerCase()))) return setup
  }
  return ''
}

function normalizeEmotionState(value: unknown, note: string): string {
  const text = String(value || '').trim()
  if (VALID_EMOTION_STATES.has(text)) return text
  if (/(控制不住|冲动|手痒|怕错过|fomo)/i.test(note)) return 'impulsive'
  if (/(报复|翻本|赚回来)/i.test(note)) return 'revenge'
  if (/(焦虑|紧张)/i.test(note)) return 'anxious'
  if (/(稳定|平静)/i.test(note)) return 'stable'
  return ''
}

function normalizePreTradeEmotion(value: unknown, note: string): string {
  const text = String(value || '').trim()
  if (VALID_PRE_TRADE_EMOTIONS.has(text)) return text
  if (/(怕错过|fomo)/i.test(note)) return 'fomo'
  if (/(控制不住|冲动|手痒|着急|急着|赶紧)/i.test(note)) return 'rushed'
  if (/(不服|硬要|硬来)/i.test(note)) return 'defiant'
  if (/(翻本|赚回来|亏损后)/i.test(note)) return 'recover_loss'
  if (/(稳定|平静)/i.test(note)) return 'stable'
  return ''
}

function normalizePostTradeEmotion(value: unknown, note: string): string {
  const text = String(value || '').trim()
  if (text && text !== 'unset' && VALID_POST_TRADE_EMOTIONS.has(text)) return text
  if (/(平仓后|出来后|出掉后).*(后悔)/i.test(note) || /后悔/.test(note)) return 'regret'
  if (/(平仓后|出来后|出掉后).*(满意|踏实)/i.test(note) || /(满意|踏实)/.test(note)) return 'satisfied'
  if (/(平仓后|出来后|出掉后).*(着急|赶紧)/i.test(note)) return 'rushed'
  if (/(平仓后|出来后|出掉后).*(不服)/i.test(note)) return 'defiant'
  if (/(平仓后|出来后|出掉后).*(稳定|平静)/i.test(note)) return 'stable'
  return ''
}
