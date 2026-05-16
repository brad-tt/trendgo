import type { DailyRecord } from '../../types'

export type WorkbenchFormState = {
  abnormalPlan: string
  capitalUsed: string
  certificateFilterNote: string
  currentState: string
  followNormalRules: boolean
  focusSetup: string
  focusTickers: string
  hkWatchlist: string
  keyReminder: string
  lowerSupport: string
  mainDirection: string
  preMarketNote: string
  preMarketState: string
  openingPlan: string
  open30KeySignal: string
  optionContractFilter: string
  optionEntrySignal: string
  optionEventRiskPlan: string
  optionFocusSetup: string
  optionRiskPlan: string
  optionSessionPlan: string
  pivotLevel: string
  playbookPreset: string
  postMarketSummary: string
  profitTargetPct: string
  tradingToday: boolean
  tradingMode: string
  upperPressure: string
  usWatchlist: string
}

export const usPlaybookPresets = {
  defensiveNoTrade: {
    focusTickers: 'SPY / QQQ',
    optionContractFilter: '价差、IV、到期日、流动性任一项不舒服就直接过滤。',
    optionEntrySignal: '只接受方向、位置、成交量、风险都清楚的 A 级机会；否则空仓。',
    optionEventRiskPlan: '重大数据或财报窗口不做临场猜方向。',
    optionFocusSetup: 'clear_observe',
    optionRiskPlan: '不靠加仓追回，连续两次低质量冲动直接停手。',
    optionSessionPlan: 'clear_no_trade',
  },
  first15Trend: {
    focusTickers: 'TSLA / NVDA / SPY / QQQ',
    optionContractFilter: '只选近月高流动性合约；价差过宽、成交稀薄、IV 异常拉高时不做。',
    optionEntrySignal: '先等前 15 分钟方向和 VWAP 关系清楚，只做放量延续或回踩不破的机会。',
    optionEventRiskPlan: '财报、FOMC、CPI、盘后消息前后默认降频；看不懂 IV 就不交易。',
    optionFocusSetup: 'orb_continuation',
    optionRiskPlan: '单笔先定义最大亏损，亏损到预设金额直接退出，不用补仓摊平。',
    optionSessionPlan: 'wait_first_15m',
  },
  vwapReclaim: {
    focusTickers: 'TSLA / NVDA',
    optionContractFilter: '优先选择流动性充足、价差可接受、delta 适中的合约。',
    optionEntrySignal: '只做价格重新站回 VWAP 后的二次确认，不追第一根放量大阳线。',
    optionEventRiskPlan: '若消息驱动跳空过大，先观察，不追第一段情绪。',
    optionFocusSetup: 'vwap_reclaim',
    optionRiskPlan: '入场前先写清失效点，跌回 VWAP 下方直接退出。',
    optionSessionPlan: 'pullback_only',
  },
} as const

export const hsiPlaybookPresets = {
  confirmedBreakout: {
    abnormalPlan: '如果开盘乱甩或假突破频繁，先暂停观察，不用第一笔证明反应速度。',
    certificateFilterNote: '只选成交活跃、价差可接受、强制收回距离安全的牛熊证；过滤不过不做。',
    focusSetup: 'opening_breakout',
    openingPlan: 'breakout_if_confirmed',
    open30KeySignal: '只看方向一致、关键位突破后有确认；没有回踩确认不抢第一笔。',
  },
  observeFirst: {
    abnormalPlan: '遇到剧烈乱甩、低质量机会连续诱惑时，回到观察模式，不临场发明新规则。',
    certificateFilterNote: '只做过滤完全通过的标的；看不懂价格跳动或价差不舒服就放弃。',
    focusSetup: 'clear_observe',
    openingPlan: 'observe_first',
    open30KeySignal: '前 30 分钟先判断主线，不急着交易；方向、位置、确认、风险任一项不清楚就等。',
  },
  pullbackConfirm: {
    abnormalPlan: '止损后如果立刻反向拉回，先确认市场是否真的变了，不因不服气反手。',
    certificateFilterNote: '优先选距离安全、波动可控的牛熊证；回踩确认前不提前埋单。',
    focusSetup: 'pullback_reclaim',
    openingPlan: 'pullback_only',
    open30KeySignal: '先等第一段方向出来，再看回踩关键位是否守住；没有二次确认不追。',
  },
} as const

export const SHARED_NO_TRADE_RULES = [
  '看不清主方向，不因为无聊、怕错过、想证明自己而硬开第一笔。',
  '位置、确认、风险、工具过滤四项里只要有一项不清楚，直接当作无效机会放弃。',
  '临近重大数据、突发消息、剧烈乱甩或价差明显失真时，先退回观察，不做情绪单。',
  '连续出现低质量诱惑时，不用"再试一笔"验证自己，当天只等 A 级机会。',
]

export const SHARED_STOP_RULES = [
  '连续两笔冲动单、报复单或明显偏离盘前计划，直接停手，不允许靠加仓追回。',
  '出现明确的强制停手事件后，当天不再开新仓，只做复盘和记录。',
  '如果身体、情绪、专注度明显不适合交易，状态切到观察或不交易，不硬撑。',
  '已经看不懂节奏、连续犹豫乱追、开始想靠下一笔翻盘时，立即结束当天执行。',
]

export function createWorkbenchForm(day: DailyRecord): WorkbenchFormState {
  const tradingMode =
    day.base.market === 'US' || day.base.primaryInstrument === 'US stock options'
      ? 'us_stock_options'
      : String(day.workbench.tradingMode ?? 'hsi_bull_bear_certificate')
  return {
    abnormalPlan: String(day.playbook.abnormalPlan ?? ''),
    capitalUsed: String(day.workbench.capitalUsed ?? ''),
    certificateFilterNote: String(day.playbook.certificateFilterNote ?? ''),
    currentState: String(day.workbench.currentState ?? 'unset'),
    followNormalRules: Boolean(day.preMarket.followNormalRules ?? true),
    focusSetup: String(day.playbook.focusSetup ?? ''),
    focusTickers: String(day.playbook.focusTickers ?? ''),
    hkWatchlist: String(day.workbench.hkWatchlist ?? ''),
    keyReminder: String(day.preMarket.keyReminder ?? ''),
    lowerSupport: String(day.workbench.lowerSupport ?? ''),
    mainDirection: String(day.workbench.mainDirection ?? 'undecided'),
    preMarketNote: String(day.preMarket.note ?? ''),
    preMarketState: String(day.preMarket.state ?? 'normal'),
    openingPlan: String(day.playbook.openingPlan ?? ''),
    open30KeySignal: String(day.playbook.open30KeySignal ?? ''),
    optionContractFilter: String(day.playbook.optionContractFilter ?? ''),
    optionEntrySignal: String(day.playbook.optionEntrySignal ?? ''),
    optionEventRiskPlan: String(day.playbook.optionEventRiskPlan ?? ''),
    optionFocusSetup: String(day.playbook.optionFocusSetup ?? ''),
    optionRiskPlan: String(day.playbook.optionRiskPlan ?? ''),
    optionSessionPlan: String(day.playbook.optionSessionPlan ?? ''),
    pivotLevel: String(day.workbench.pivotLevel ?? ''),
    playbookPreset: '',
    postMarketSummary: String(day.workbench.postMarketSummary ?? ''),
    profitTargetPct: String(day.workbench.profitTargetPct ?? ''),
    tradingToday: Boolean(day.preMarket.tradingToday ?? true),
    tradingMode,
    upperPressure: String(day.workbench.upperPressure ?? ''),
    usWatchlist: String(day.workbench.usWatchlist ?? ''),
  }
}

export function formatTodayTradeDate() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
