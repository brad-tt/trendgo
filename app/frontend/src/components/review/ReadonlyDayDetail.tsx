import type { DailyRecord, RuleEvent, Trade } from '../../types'
import { displayValue, formatTradeDate } from '../../utils/display'
import { formatHkdSummaryAmount, formatTradePnl, sumTradesPnlHkd, winRateText } from '../../utils/money'
import { Badge } from '../ui/Badge'
import { MetaRow } from '../ui/MetaRow'
import { pnlToneClass } from './reviewUtils'

function DetailMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-toptrader-line bg-toptrader-soft/45 px-4 py-3">
      <p className="text-xs font-medium text-toptrader-muted">{label}</p>
      <p className="mt-1 text-lg font-bold text-toptrader-accent">{value}</p>
    </div>
  )
}

function ReadonlyNote({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-toptrader-line bg-toptrader-panel px-4 py-4">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-toptrader-muted">{label}</p>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-toptrader-accent">{value || '--'}</p>
    </div>
  )
}

function ReadonlyTradeList({ trades }: { trades: Trade[] }) {
  return (
    <section>
      <h5 className="font-display text-lg font-bold text-toptrader-accent">交易记录</h5>
      <div className="mt-3 space-y-3">
        {trades.length ? (
          trades.map((trade) => {
            const pnl = formatTradePnl(trade)
            return (
              <div key={trade.tradeId} className="rounded-2xl border border-toptrader-line bg-toptrader-soft/35 px-4 py-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-toptrader-accent">{trade.tradeId}</p>
                    <p className="mt-1 text-xs text-toptrader-muted">
                      {(trade.tradeTime || '未填开仓')} → {(trade.exitTime || '未填平仓')}
                    </p>
                  </div>
                  <p className={['text-sm font-bold', pnlToneClass(trade.pnlAmount)].join(' ')}>
                    {pnl.primary}
                  </p>
                </div>
                <p className="mt-2 text-sm leading-6 text-toptrader-muted">
                  {trade.instrumentCode || '--'} / {displayValue(trade.direction)} / {displayValue(trade.setupType)} / {displayValue(trade.certificateSide)}
                </p>
                <p className="mt-1 text-sm leading-6 text-toptrader-muted">{trade.entryReason || '未填写入场说明'}</p>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <MetaRow label="标的类型" value={displayValue(trade.instrumentType)} />
                  <MetaRow label="相关标的" value={trade.underlying || '--'} />
                  <MetaRow label="持仓数量" value={trade.positionSize || '--'} />
                  <MetaRow label="入场价 / 止损 / 目标" value={`${displayNumber(trade.entryPrice)} / ${displayNumber(trade.stopLoss)} / ${displayNumber(trade.targetPrice)}`} />
                  <MetaRow label="出场价 / 风报比" value={`${displayNumber(trade.exitPrice)} / ${displayNumber(trade.riskRewardRatio)}`} />
                  <MetaRow label="结果 / 评级" value={`${displayValue(trade.result)} / ${displayValue(trade.abcGrade)}`} />
                  <MetaRow label="是否按计划" value={trade.followedPlan ? '是' : '否'} />
                  <MetaRow label="规则违规" value={trade.ruleViolation ? '是' : '否'} />
                  <MetaRow label="异常场景" value={displayValue(trade.abnormalScenario)} />
                  <MetaRow label="过滤通过" value={nullableBoolText(trade.certificateFilterPassed)} />
                  <MetaRow label="形态验证 / 评分" value={`${nullableBoolText(trade.setupValidated)} / ${displayNumber(trade.setupScore)}`} />
                  <MetaRow label="方向清晰 / 位置合适" value={`${nullableBoolText(trade.directionClear)} / ${nullableBoolText(trade.locationOk)}`} />
                  <MetaRow label="确认充分 / 风险清晰" value={`${nullableBoolText(trade.confirmationOk)} / ${nullableBoolText(trade.riskClear)}`} />
                  <MetaRow label="盘前情绪 / 盘后情绪" value={`${displayValue(trade.preTradeEmotion)} / ${displayValue(trade.postTradeEmotion)}`} />
                  <MetaRow label="盘中情绪状态" value={displayValue(trade.emotionState)} />
                  <MetaRow label="出场原因" value={trade.exitReason || '--'} />
                  <MetaRow label="复盘备注" value={trade.reviewNote || '--'} />
                  <MetaRow label="截图备注" value={trade.screenshotNote || '--'} />
                  <MetaRow label="违规备注" value={trade.violationNote || '--'} />
                  <MetaRow label="交易时段" value={displayValue(trade.sessionWindow)} />
                </div>
              </div>
            )
          })
        ) : (
          <p className="rounded-2xl border border-toptrader-line bg-toptrader-soft/35 px-4 py-4 text-sm text-toptrader-muted">
            当天没有交易记录。
          </p>
        )}
      </div>
    </section>
  )
}

function ReadonlyEventList({ events }: { events: RuleEvent[] }) {
  return (
    <section>
      <h5 className="font-display text-lg font-bold text-toptrader-accent">纪律事件</h5>
      <div className="mt-3 space-y-3">
        {events.length ? (
          events.map((event) => (
            <div key={event.eventId} className="rounded-2xl border border-toptrader-line bg-toptrader-panel px-4 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-toptrader-accent">{event.eventId}</p>
                  <p className="mt-1 text-xs text-toptrader-muted">
                    {event.time || '--'} / {displayValue(event.severity)}
                  </p>
                </div>
                <Badge label={displayValue(event.eventType)} />
              </div>
              <p className="mt-2 text-sm leading-6 text-toptrader-muted">{event.triggerReason || '--'}</p>
              <div className="mt-3 grid gap-2">
                <MetaRow label="处理动作" value={displayValue(event.actionTaken)} />
                <MetaRow label="关联交易" value={event.linkedTradeId || '--'} />
                <MetaRow label="后续跟进" value={event.followUpNote || '--'} />
              </div>
            </div>
          ))
        ) : (
          <p className="rounded-2xl border border-toptrader-line bg-toptrader-panel px-4 py-4 text-sm text-toptrader-muted">
            当天没有纪律事件。
          </p>
        )}
      </div>
    </section>
  )
}

export function ReadonlyDayDetail({
  day,
  error,
  loading,
  selectedRecordPath,
}: {
  day: DailyRecord | null
  error: string
  loading: boolean
  selectedRecordPath: string
}) {
  if (!selectedRecordPath) {
    return (
      <section className="mt-5 rounded-2xl border border-dashed border-toptrader-line bg-toptrader-panel/70 px-5 py-5 text-sm text-toptrader-muted">
        点击上方交易日，查看当天只读复盘、交易记录和纪律事件。
      </section>
    )
  }

  if (loading) {
    return (
      <section className="mt-5 rounded-2xl border border-toptrader-brand/20 bg-toptrader-brand/10 px-5 py-5 text-sm text-toptrader-brand">
        正在加载历史复盘…
      </section>
    )
  }

  if (error) {
    return (
      <section className="mt-5 rounded-2xl border border-toptrader-rose/30 bg-toptrader-rose/10 px-5 py-5 text-sm text-toptrader-rose">
        {error}
      </section>
    )
  }

  if (!day) {
    return null
  }

  const pnlHkd = sumTradesPnlHkd(day.trades)
  const modeText = displayValue(day.base.market === 'US' ? 'us_stock_options' : day.workbench.tradingMode)

  return (
    <section className="mt-5 rounded-2xl border border-toptrader-line bg-toptrader-panel px-5 py-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="font-display text-xl font-bold text-toptrader-accent">
            {formatTradeDate(day.base.tradeDate)}
          </h4>
          <p className="mt-2 text-sm text-toptrader-muted">
            {displayValue(day.base.market)} / {modeText}
          </p>
        </div>
        <Badge label={day.isCurrent ? '当日交易日' : '历史只读'} tone={day.isCurrent ? 'success' : 'neutral'} />
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-4">
        <DetailMetric label="交易数" value={day.trades.length} />
        <DetailMetric label="纪律事件" value={day.events.length} />
        <DetailMetric label="盈亏" value={formatHkdSummaryAmount(pnlHkd)} />
        <DetailMetric label="胜率" value={winRateText(day.trades)} />
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border border-toptrader-line bg-toptrader-soft/35 px-4 py-4">
          <h5 className="font-display text-base font-bold text-toptrader-accent">基础 / 盘前 / 作战台</h5>
          <div className="mt-3 grid gap-2">
            <MetaRow label="交易日 / 市场" value={`${formatTradeDate(day.base.tradeDate)} / ${displayValue(day.base.market)}`} />
            <MetaRow label="操作者 / 记录归属" value={`${day.base.operator || '--'} / ${day.base.recordOwner || '--'}`} />
            <MetaRow label="主交易工具" value={displayValue(day.base.primaryInstrument)} />
            <MetaRow label="盘前状态" value={displayValue(day.preMarket.state)} />
            <MetaRow label="今日交易" value={day.preMarket.tradingToday ? '是' : '否'} />
            <MetaRow label="遵守常规规则" value={day.preMarket.followNormalRules ? '是' : '否'} />
            <MetaRow label="关键提醒" value={day.preMarket.keyReminder || '--'} />
            <MetaRow label="盘前备注" value={day.preMarket.note || '--'} />
            <MetaRow label="当前状态" value={displayValue(day.workbench.currentState)} />
            <MetaRow label="交易模式" value={displayValue(day.workbench.tradingMode)} />
            <MetaRow label="主方向" value={displayValue(day.workbench.mainDirection)} />
            <MetaRow label="使用本金 / 目标%" value={`${displayNumber(day.workbench.capitalUsed)} / ${displayNumber(day.workbench.profitTargetPct)}`} />
            <MetaRow label="上方压力 / 下方支撑" value={`${day.workbench.upperPressure || '--'} / ${day.workbench.lowerSupport || '--'}`} />
            <MetaRow label="枢轴位" value={day.workbench.pivotLevel || '--'} />
            <MetaRow label="港股观察列表" value={day.workbench.hkWatchlist || '--'} />
            <MetaRow label="美股观察列表" value={day.workbench.usWatchlist || '--'} />
            <MetaRow label="盘后总结" value={day.workbench.postMarketSummary || '--'} />
          </div>
        </section>

        <section className="rounded-2xl border border-toptrader-line bg-toptrader-panel px-4 py-4">
          <h5 className="font-display text-base font-bold text-toptrader-accent">交易计划 / 验证 / 归档</h5>
          <div className="mt-3 grid gap-2">
            <MetaRow label="开盘计划" value={displayValue(day.playbook.openingPlan)} />
            <MetaRow label="主练形态 / 期权主练形态" value={`${displayValue(day.playbook.focusSetup)} / ${displayValue(day.playbook.optionFocusSetup)}`} />
            <MetaRow label="关注标的" value={day.playbook.focusTickers || '--'} />
            <MetaRow label="开盘 30 分钟信号" value={day.playbook.open30KeySignal || '--'} />
            <MetaRow label="过滤备注" value={day.playbook.certificateFilterNote || '--'} />
            <MetaRow label="异常场景预案" value={day.playbook.abnormalPlan || '--'} />
            <MetaRow label="期权时段计划" value={displayValue(day.playbook.optionSessionPlan)} />
            <MetaRow label="期权入场信号" value={day.playbook.optionEntrySignal || '--'} />
            <MetaRow label="期权合约过滤" value={day.playbook.optionContractFilter || '--'} />
            <MetaRow label="期权风控计划" value={day.playbook.optionRiskPlan || '--'} />
            <MetaRow label="期权事件风险计划" value={day.playbook.optionEventRiskPlan || '--'} />
            <MetaRow label="盘前 / 盘中 / 盘后完成" value={`${boolText(day.validation.preMarketDone)} / ${boolText(day.validation.intradayRecordComplete)} / ${boolText(day.validation.postMarketReviewDone)}`} />
            <MetaRow label="冲动 / 止损失守 / 过度交易" value={`${boolText(day.validation.impulsiveTradeDetected)} / ${boolText(day.validation.noStopLossTradeDetected)} / ${boolText(day.validation.emotionalOvertradeDetected)}`} />
            <MetaRow label="空仓日 / 说明" value={`${boolText(day.validation.noTradeDay)} / ${day.validation.noTradeNote || '--'}`} />
            <MetaRow label="主要问题" value={day.validation.mainIssueOfDay || '--'} />
            <MetaRow label="主要改进" value={day.validation.mainImprovementOfDay || '--'} />
            <MetaRow label="归档状态" value={day.closeout.exists ? (day.closeout.stale ? '已生成但待更新' : '已生成且同步') : '未生成'} />
            <MetaRow label="归档路径" value={day.closeout.path || '--'} />
          </div>
        </section>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <ReadonlyNote label="最好动作" value={day.review.bestTradeNote} />
        <ReadonlyNote label="最差问题" value={day.review.worstTradeNote} />
        <ReadonlyNote label="执行问题" value={day.review.executionIssue} />
        <ReadonlyNote label="情绪问题" value={day.review.emotionIssue} />
        <ReadonlyNote label="风控问题" value={day.review.riskIssue} />
        <ReadonlyNote label="明天只改" value={day.review.nextDayOneFix} />
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(260px,0.8fr)]">
        <ReadonlyTradeList trades={day.trades} />
        <ReadonlyEventList events={day.events} />
      </div>
    </section>
  )
}

function boolText(value: boolean) {
  return value ? '是' : '否'
}

function nullableBoolText(value: boolean | null) {
  if (value === null) return '--'
  return value ? '是' : '否'
}

function displayNumber(value: number | null) {
  if (value === null || value === undefined) {
    return '--'
  }
  return String(value)
}
