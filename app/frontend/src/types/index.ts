export interface ArtifactItem {
  title: string
  path: string
}

export interface RecentRecordItem {
  closeoutLabel: string
  currentState: string
  dayNumber?: number
  isCurrent: boolean
  market: string
  primaryInstrument: string
  reviewDone: boolean
  sourceRecordPath: string
  tradeCount: number
  tradeDate: string
  tradingMode: string
  validationDone: boolean
}

export interface AppState {
  currentMarket: 'HK' | 'US'
  currentAuditPath: string
  currentCloseoutPath: string
  currentDayNumber: number | null
  currentRecordPath: string
  currentSummaryPath: string
  currentTradeDate: string
  theme: 'dark' | 'light'
  todayRecords: {
    HK: boolean
    US: boolean
  }
  recentAudits: ArtifactItem[]
  recentCloseouts: ArtifactItem[]
  recentRecords: RecentRecordItem[]
  recentSummaries: ArtifactItem[]
  reviewHubSampleFilter: string
  reviewHubWindow: string
  usdHkdRate: number
}

export interface CloseoutPayload {
  exists: boolean
  legacy: boolean
  path: string
  preview: string
  stale: boolean
}

export interface BaseFields {
  dayNumber?: number
  market: string
  operator: string
  primaryInstrument: string
  recordMode: string
  recordOwner: string
  tradeDate: string
}

export interface PreMarketFields {
  followNormalRules: boolean
  keyReminder: string
  note: string
  state: string
  tradingToday: boolean
}

export interface WorkbenchFields {
  capitalUsed: number | null
  currentState: string
  hkWatchlist: string
  lowerSupport: string
  mainDirection: string
  pivotLevel: string
  postMarketSummary: string
  profitTargetPct: number | null
  tradingMode: string
  upperPressure: string
  usWatchlist: string
}

export interface PlaybookFields {
  abnormalPlan: string
  certificateFilterNote: string
  focusSetup: string
  focusTickers: string
  openingPlan: string
  open30KeySignal: string
  optionContractFilter: string
  optionEntrySignal: string
  optionEventRiskPlan: string
  optionFocusSetup: string
  optionRiskPlan: string
  optionSessionPlan: string
}

export interface ReviewFields {
  bestTradeNote: string
  emotionIssue: string
  executionIssue: string
  market: string
  marketIssue: string
  maxLossTrade: string
  nextDayOneFix: string
  pnl: string
  primaryInstrument: string
  reviewDate: string
  riskIssue: string
  setupIssue: string
  tradeCount: number | null
  winRate: string
  worstTradeNote: string
}

export interface ValidationFields {
  date: string
  emotionalOvertradeDetected: boolean
  impulsiveTradeDetected: boolean
  intradayRecordComplete: boolean
  mainImprovementOfDay: string
  mainIssueOfDay: string
  market: string
  noStopLossTradeDetected: boolean
  noTradeDay: boolean
  noTradeNote: string
  postMarketReviewDone: boolean
  preMarketDone: boolean
  primaryInstrument: string
  trialDayNumber?: number
}

export interface Trade {
  abcGrade: string
  abnormalScenario: string
  certificateFilterPassed: boolean | null
  certificateSide: string
  confirmationOk: boolean | null
  currency: 'HKD' | 'USD'
  direction: string
  directionClear: boolean | null
  emotionState: string
  entryPrice: number | null
  entryReason: string
  exitPrice: number | null
  exitReason: string
  exitTime: string
  followedPlan: boolean
  instrumentCode: string
  instrumentType: string
  locationOk: boolean | null
  pnlAmount: number | null
  pnlAmountHkd: number | null
  positionSize: string
  postTradeEmotion: string
  preTradeEmotion: string
  result: string
  reviewNote: string
  riskClear: boolean | null
  riskRewardRatio: number | null
  ruleViolation: boolean
  screenshotNote: string
  sessionWindow: string
  setupScore: number | null
  setupType: string
  setupValidated: boolean | null
  stopLoss: number | null
  targetPrice: number | null
  tradeDate: string
  tradeId: string
  tradeTime: string
  underlying: string
  violationNote: string
}

export interface RuleEvent {
  actionTaken: string
  date: string
  eventId: string
  eventType: string
  followUpNote: string
  linkedTradeId: string
  market: string
  severity: string
  time: string
  triggerReason: string
}

export interface AgentObservation {
  evidence: string
  linkedEventId: string
  linkedTradeId: string
  market: string
  observationId: string
  observationType: string
  reviewRequired: boolean
  severity: string
  source: string
  status: string
  summary: string
  tradeDate: string
  userResponse: string
}

export interface DailyRecord {
  base: BaseFields
  closeout: CloseoutPayload
  events: RuleEvent[]
  isCurrent: boolean
  observations: AgentObservation[]
  playbook: PlaybookFields
  preMarket: PreMarketFields
  review: ReviewFields
  sourceRecordPath: string
  trades: Trade[]
  validation: ValidationFields
  workbench: WorkbenchFields
}

export interface CountItem {
  count: number
  label: string
}

export interface TimelineNote {
  dayNumber?: number
  note: string
  tradeDate: string
}

export interface ReviewHubStats {
  abnormalTradeCount: number
  avgDailyPnl: number | null
  breakevenCount: number
  certificateFilterFailCount: number
  closeoutSyncedDays: number
  dayCount: number
  followedTotal: number
  followedYes: number
  impulsiveDays: number
  lossCount: number
  noTradeDayCount: number
  opening30TradeCount: number
  overtradeDays: number
  phase2CheckFailCount: number
  planFollowRate: number | null
  recentFixes: TimelineNote[]
  recentIssues: TimelineNote[]
  recentNoTradeNotes: TimelineNote[]
  reviewDoneDays: number
  stopLossDays: number
  topActivePlans: CountItem[]
  topActiveSetups: CountItem[]
  topSetups: CountItem[]
  totalPnl: number | null
  tradeCount: number
  tradeDayCount: number
  validationDoneDays: number
  violationCount: number
  winCount: number
}

export interface ReviewHubDayRow {
  abnormalCount: number
  activePlan: string
  activeSetup: string
  certificateFilterFailCount: number
  closeoutLabel: string
  closeoutSynced: boolean
  day?: number
  breakevenCount: number
  followedTotal: number
  followedYes: number
  hasTrades: boolean
  impulsiveFlag: boolean
  isCurrent: boolean
  isEditable: boolean
  lossCount: number
  mainImprovement: string
  mainIssue: string
  market: string
  nextFix: string
  noTradeDay: boolean
  noTradeNote: string
  opening30Count: number
  overtradeFlag: boolean
  path: string
  phase2CheckFailCount: number
  pnlValue: number | null
  qualityIssues: string[]
  reviewDone: boolean
  state: string
  stopLossFlag: boolean
  tradeCount: number
  tradeDate: string
  tradingMode: string
  trustedSample: boolean
  validationDone: boolean
  violationCount: number
  winCount: number
  workbenchReady: boolean
}

export interface HSIRangeSnapshot {
  highPrice: number | null
  lastPrice: number | null
  lowPrice: number | null
  openPrice: number | null
  turnover: number | null
  updateTime: string
}

export interface HSIRangeIntraday {
  p75LeftPct: number
  p75LeftPoints: number
  p90LeftPct: number
  p90LeftPoints: number
  positionPct: number
  rangePct: number
  rangePoints: number
  rankPct: number
}

export interface HSIRangeStatus {
  label: string
  level: string
  message: string
}

export interface HSIRangeStats {
  endDate: string
  lookback: number
  maxPct: number
  maxPoints: number
  meanPct: number
  meanPoints: number
  medianPct: number
  medianPoints: number
  p75Pct: number
  p75Points: number
  p90Pct: number
  p90Points: number
  startDate: string
}

export interface HSIRangeState {
  code: string
  error: string
  generatedAt: string
  intraday: HSIRangeIntraday | null
  name: string
  ok: boolean
  snapshot: HSIRangeSnapshot | null
  stats: HSIRangeStats | null
  status: HSIRangeStatus | null
  warnings: string[]
}

export interface DayActionResponse {
  autoEventId?: string
  day: DailyRecord
  message: string
}

export interface StateActionResponse {
  message: string
  state: AppState
}

export interface TodoItem {
  text: string
  target: string
}

export interface WorkflowStep {
  label: string
  note: string
  target: string
  done: boolean
}

export interface HealthItem {
  level: string
  text: string
  target: string
}

export interface DecisionStatus {
  status: string
  label: string
  action: string
  blockers: string[]
  cautions: string[]
  strengths: string[]
}

export interface RiskStatus {
  status: string
  label: string
  action: string
  blockers: string[]
  cautions: string[]
  strengths: string[]
  pnlTotal: number | null
  targetAmount: number | null
  tradeCount: number
  filterLabel: string
}

export interface ExecutionLock {
  status: string
  label: string
  action: string
  reasons: string[]
}

export interface DaySummary {
  capitalUsed: string
  profitTargetPct: string
  pnlTotal: string
  pnlPct: string
  targetDistance: string
  tradeCount: string
  violationCount: string
  gradeCounts: string
}

export interface ReviewDefaults {
  pnl: string
  tradeCount: string
  pnlHint: string
  tradeCountHint: string
}

export interface PreviousContext {
  day: string
  tradeDate: string
  tradingMode: string
  nextFix: string
  improvement: string
  mainIssue: string
  plan: string
  setup: string
}

export interface DayDiagnostics {
  todoItems: TodoItem[]
  workflowSteps: WorkflowStep[]
  recordHealthItems: HealthItem[]
  decisionGate: DecisionStatus
  riskState: RiskStatus
  executionLock: ExecutionLock
  daySummary: DaySummary
  reviewDefaults: ReviewDefaults
  previousContext: PreviousContext
}

export interface WorkspaceOverview {
  state: AppState
  currentDay: DailyRecord | null
  diagnostics: DayDiagnostics | null
}

export interface ArtifactsOverview {
  currentCloseout: ArtifactPreview
  currentSummary: ArtifactPreview
  currentAudit: ArtifactPreview
  recentCloseouts: ArtifactItem[]
  recentSummaries: ArtifactItem[]
  recentAudits: ArtifactItem[]
}

export interface ArtifactPreview {
  path: string
  title: string
  exists: boolean
  preview: string
}

export interface HistoryOverview {
  window: string
  sampleFilter: string
  stats: ReviewHubStats
  days: ReviewHubDayRow[]
}

export interface AgentContextToday {
  date: string
  market: string
  sessionStatus: string
  sessionLabel: string
  tradingMode: string
  mainDirection: string
  planSummary: string
  intradayPnl: number | null
  tradesDone: number
  violationsToday: number
  reviewDone: boolean
  validationDone: boolean
  nextAction: string
}

export interface AgentContextRecentPatterns {
  topDistortions: string[]
  highRiskContexts: string[]
  weeklyFocus: string
  recentIssue: string
  recentFix: string
}

export interface AgentContextStage {
  currentStage: string
  stageLabel: string
  progress: number
  stageDescription: string
}

export interface AgentContext {
  today: AgentContextToday
  recentPatterns: AgentContextRecentPatterns
  stage: AgentContextStage
}

export interface AgentWorkflowResult {
  message: string
  rawNote?: string
  proposal?: Record<string, unknown>
  missingFields?: string[]
  missingLabels?: string[]
  warnings?: string[]
  followUpQuestions?: string[]
  ruleHits?: Array<Record<string, unknown>>
  knowledgeRoutes?: Array<Record<string, unknown>>
  canWrite?: boolean
  committed?: boolean
  targetTradeId?: string
  resultPreview?: string
  day?: DailyRecord
}

export interface AgentWorkflowResponse {
  message: string
  intent: string
  intentConfidence: number
  suggestedEndpoint: string
  nextAction: string
  context: AgentContext
  result: AgentWorkflowResult
}

export interface AgentSessionResponse {
  message: string
  intent: string
  intentConfidence: number
  nextAction: string
  autoCommitted: boolean
  context: AgentContext
  workflow: AgentWorkflowResponse
}
