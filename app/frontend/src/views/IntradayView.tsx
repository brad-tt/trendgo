import { RuleEventPanel } from '../components/review/RuleEventPanel'
import { TradePanel } from '../components/review/TradePanel'
import { Badge } from '../components/ui/Badge'
import { MetaRow } from '../components/ui/MetaRow'
import { useWorkspaceData } from '../hooks/useWorkspaceData'
import { displayValue } from '../utils/display'
import { formatHkdSummaryAmount, sumTradesPnlHkd } from '../utils/money'

export function IntradayView() {
  const { day, error, loading, setDay } = useWorkspaceData()

  if (loading && !day) {
    return <Placeholder text="正在加载盘中执行视图…" />
  }

  if (!day) {
    return <Placeholder text={error || '当前没有可编辑交易日。'} />
  }

  const pnlHkd = sumTradesPnlHkd(day.trades)
  const tradeCount = day.trades.length
  const eventCount = day.events.length
  const violationCount = day.trades.filter((trade) => trade.ruleViolation).length
  const abnormalCount = day.trades.filter((trade) => trade.abnormalScenario && trade.abnormalScenario !== 'none').length
  const filterFailCount = day.trades.filter((trade) => trade.certificateFilterPassed === false).length
  const opening30Count = day.trades.filter((trade) => trade.sessionWindow === 'opening_30m').length
  const winCount = day.trades.filter((trade) => trade.result === 'win').length
  const lossCount = day.trades.filter((trade) => trade.result === 'loss').length
  const diagnostics = buildIntradayDiagnostics(day.trades, day.events.length, pnlHkd)
  const topTrades = [...day.trades]
    .sort((left, right) => (right.pnlAmountHkd ?? right.pnlAmount ?? -Infinity) - (left.pnlAmountHkd ?? left.pnlAmount ?? -Infinity))
    .slice(0, 3)
  const riskTrades = [...day.trades]
    .filter(
      (trade) =>
        trade.ruleViolation ||
        trade.abnormalScenario !== 'none' ||
        trade.certificateFilterPassed === false ||
        trade.followedPlan === false,
    )
    .slice(0, 3)

  return (
    <section className="space-y-3">
      <div>
        <h2 className="tt-heading-page">盘中执行</h2>
      </div>

      <section className="tt-bento-panel">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="tt-heading-card">盘中概览</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge label={`交易 ${tradeCount}`} tone="success" />
            <Badge label={`事件 ${eventCount}`} />
            <Badge label={`盈亏 ${formatHkdSummaryAmount(pnlHkd)}`} tone={pnlHkd > 0 ? 'success' : pnlHkd < 0 ? 'danger' : 'neutral'} />
          </div>
        </div>
        <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.95fr)]">
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <CompactMetricCard label="当日盈亏(HKD)" tone={pnlHkd > 0 ? 'success' : pnlHkd < 0 ? 'danger' : 'neutral'} value={formatHkdSummaryAmount(pnlHkd)} />
              <CompactMetricCard label="交易数" value={String(tradeCount)} />
              <CompactMetricCard label="纪律事件数" value={String(eventCount)} />
              <CompactMetricCard label="按计划执行" value={tradeCount ? `${tradeCount - day.trades.filter((trade) => !trade.followedPlan).length} / ${tradeCount}` : '--'} />
              <CompactMetricCard label="违规交易数" value={String(violationCount)} />
              <CompactMetricCard label="异常场景交易" value={String(abnormalCount)} />
              <CompactMetricCard label="过滤失败数" value={String(filterFailCount)} />
              <CompactMetricCard label="开盘时段交易" value={String(opening30Count)} />
              <CompactMetricCard label="赢 / 亏" value={`${winCount} / ${lossCount}`} />
              <CompactMetricCard label="主练形态" value={displayValue(day.playbook.focusSetup)} />
              <CompactMetricCard label="开盘计划" value={displayValue(day.playbook.openingPlan)} />
              <CompactMetricCard label="开盘 30 分钟信号" value={day.playbook.open30KeySignal || '--'} />
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <MetaPanel label="异常场景预案" value={day.playbook.abnormalPlan || '--'} />
              <MetaPanel label="当前固定约束" value={`过滤失败 ${filterFailCount} / 异常场景 ${abnormalCount} / 纪律事件 ${eventCount}`} />
            </div>
          </div>
          <div className="grid gap-3">
            <StatusPanel
              action={diagnostics.execution.action}
              details={diagnostics.execution.reasons}
              label={diagnostics.execution.label}
              title="执行状态"
              tone={diagnostics.execution.tone}
            />
            <StatusPanel
              action={diagnostics.risk.action}
              details={diagnostics.risk.reasons}
              label={diagnostics.risk.label}
              title="风险状态"
              tone={diagnostics.risk.tone}
            />
            <ChecklistPanel
              items={diagnostics.todos}
              title="下一步动作"
            />
          </div>
        </div>
      </section>

      <section className="tt-bento-grid">
        <div className="col-span-12 xl:col-span-8 space-y-3">
          <TradePanel day={day} onDayChange={(updatedDay) => void setDay(updatedDay)} />

          <section className="tt-bento-panel">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="tt-heading-card">关键交易样本</h3>
              </div>
              <Badge label="辅助视图" />
            </div>
            <div className="mt-4 grid gap-3 xl:grid-cols-2">
              <SampleGroup
                emptyText="当前还没有可展示的高收益样本。"
                title="高收益样本"
                trades={topTrades}
              />
              <SampleGroup
                emptyText="当前还没有明显偏离计划的高风险样本。"
                title="高风险样本"
                trades={riskTrades}
              />
            </div>
          </section>
        </div>

        <div className="col-span-12 xl:col-span-4 space-y-3">
          <RuleEventPanel
            events={day.events}
            isCurrent={day.isCurrent}
            market={day.base.market}
            onEventsChange={(updatedDay) => void setDay(updatedDay)}
            tradeDate={day.base.tradeDate}
            tradeIds={day.trades.map((trade) => trade.tradeId)}
          />
        </div>
      </section>
    </section>
  )
}

function Placeholder({ text }: { text: string }) {
  return <section className="tt-card p-6 text-sm text-toptrader-muted">{text}</section>
}

function CompactMetricCard({
  label,
  tone = 'neutral',
  value,
}: {
  label: string
  tone?: 'success' | 'warning' | 'danger' | 'neutral'
  value: string
}) {
  const toneClass =
    tone === 'success'
      ? 'border-toptrader-brand/25 bg-toptrader-brand/8'
      : tone === 'warning'
        ? 'border-amber-500/25 bg-amber-500/8'
        : tone === 'danger'
          ? 'border-toptrader-rose/25 bg-toptrader-rose/8'
          : 'border-toptrader-line bg-toptrader-panel/92'

  return (
    <div className={['min-h-[72px] rounded-xl border px-2.5 py-2.5', toneClass].join(' ')}>
      <div className="text-[9px] font-semibold uppercase tracking-[0.08em] text-toptrader-muted">{label}</div>
      <div className="mt-0.5 text-[15px] font-bold leading-6 text-toptrader-accent">{value}</div>
    </div>
  )
}

function MetaPanel({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-toptrader-line bg-toptrader-panel/92 px-2.5 py-2.5">
      <div className="text-[9px] font-semibold uppercase tracking-[0.08em] text-toptrader-muted">{label}</div>
      <div className="mt-0.5 text-[11px] leading-5 text-toptrader-accent">{value}</div>
    </div>
  )
}

function StatusPanel({
  action,
  details,
  label,
  title,
  tone,
}: {
  action: string
  details: string[]
  label: string
  title: string
  tone: 'success' | 'warning' | 'danger' | 'neutral'
}) {
  return (
    <div className="rounded-xl border border-toptrader-line bg-toptrader-panel px-2.5 py-2.5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[13px] font-semibold text-toptrader-accent">{title}</div>
          <div className="mt-0.5 text-[11px] text-toptrader-muted">{action || '--'}</div>
        </div>
        <Badge label={label || '--'} tone={tone} />
      </div>
      <div className="mt-2.5 space-y-1.5">
        {details.length ? details.map((detail) => <div key={detail} className="rounded-lg bg-toptrader-soft/55 px-2 py-1.5 text-[11px] leading-5 text-toptrader-ink">{detail}</div>) : <div className="text-[11px] text-toptrader-muted">暂无额外信号。</div>}
      </div>
    </div>
  )
}

function ChecklistPanel({
  items,
  title,
}: {
  items: string[]
  title: string
}) {
  return (
    <div className="rounded-xl border border-toptrader-line bg-toptrader-panel px-2.5 py-2.5">
      <div className="text-[13px] font-semibold text-toptrader-accent">{title}</div>
      <div className="mt-2.5 space-y-1.5">
        {items.length ? items.map((item) => <div key={item} className="rounded-lg bg-toptrader-soft/55 px-2 py-1.5 text-[11px] leading-5 text-toptrader-ink">{item}</div>) : <div className="text-[11px] text-toptrader-muted">当前无新增待办。</div>}
      </div>
    </div>
  )
}

function TradeSnapshotCard({
  trade,
}: {
  trade: {
    abnormalScenario: string
    certificateFilterPassed: boolean | null
    direction: string
    emotionState: string
    followedPlan: boolean
    instrumentCode: string
    pnlAmountHkd: number | null
    pnlAmount: number | null
    preTradeEmotion: string
    result: string
    reviewNote: string
    ruleViolation: boolean
    setupType: string
    tradeId: string
    tradeTime: string
  }
}) {
  return (
    <div className="rounded-xl border border-toptrader-line bg-toptrader-panel/88 px-2.5 py-2.5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="mt-0.5 text-[13px] font-semibold text-toptrader-accent">{trade.tradeId}</div>
        </div>
        <Badge
          label={trade.ruleViolation ? '含违规' : displayValue(trade.result)}
          tone={trade.ruleViolation ? 'danger' : trade.result === 'win' ? 'success' : trade.result === 'loss' ? 'warning' : 'neutral'}
        />
      </div>
      <div className="mt-2.5 grid gap-1.5">
        <MetaRow label="标的 / 时间" value={`${trade.instrumentCode || '--'} / ${trade.tradeTime || '--'}`} />
        <MetaRow label="方向 / 形态" value={`${displayValue(trade.direction)} / ${displayValue(trade.setupType)}`} />
        <MetaRow label="盈亏(HKD)" value={formatHkdSummaryAmount(trade.pnlAmountHkd ?? trade.pnlAmount)} />
        <MetaRow label="是否按计划" value={trade.followedPlan ? '是' : '否'} />
        <MetaRow label="过滤通过" value={nullableBoolText(trade.certificateFilterPassed)} />
        <MetaRow label="异常场景" value={displayValue(trade.abnormalScenario)} />
        <MetaRow label="盘前情绪 / 盘中情绪" value={`${displayValue(trade.preTradeEmotion)} / ${displayValue(trade.emotionState)}`} />
        <MetaRow label="复盘备注" value={trade.reviewNote || '--'} />
      </div>
    </div>
  )
}

function EmptyCard({ text }: { text: string }) {
  return <div className="rounded-xl border border-dashed border-toptrader-line bg-toptrader-panel/70 px-3 py-6 text-sm text-toptrader-muted">{text}</div>
}

function SampleGroup({
  emptyText,
  title,
  trades,
}: {
  emptyText: string
  title: string
  trades: Array<{
    abnormalScenario: string
    certificateFilterPassed: boolean | null
    direction: string
    emotionState: string
    followedPlan: boolean
    instrumentCode: string
    pnlAmountHkd: number | null
    pnlAmount: number | null
    preTradeEmotion: string
    result: string
    reviewNote: string
    ruleViolation: boolean
    setupType: string
    tradeId: string
    tradeTime: string
  }>
}) {
  return (
    <section className="rounded-xl border border-toptrader-line bg-toptrader-soft/20 px-2.5 py-2.5">
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-toptrader-muted">{title}</div>
      <div className="mt-2.5 space-y-2">
        {trades.length ? trades.map((trade) => <TradeSnapshotCard key={`${title}-${trade.tradeId}`} trade={trade} />) : <EmptyCard text={emptyText} />}
      </div>
    </section>
  )
}

function nullableBoolText(value: boolean | null) {
  if (value === null) return '--'
  return value ? '是' : '否'
}

function buildIntradayDiagnostics(
  trades: Array<{
    abnormalScenario: string
    certificateFilterPassed: boolean | null
    followedPlan: boolean
    ruleViolation: boolean
  }>,
  eventCount: number,
  pnlHkd: number,
) {
  const violationCount = trades.filter((trade) => trade.ruleViolation).length
  const abnormalCount = trades.filter((trade) => trade.abnormalScenario !== 'none').length
  const filterFailCount = trades.filter((trade) => trade.certificateFilterPassed === false).length
  const unfollowedCount = trades.filter((trade) => !trade.followedPlan).length

  const execution =
    violationCount >= 2 || eventCount >= 3
      ? {
          action: '优先停止新增交易，先处理纪律偏离。',
          label: '建议停手',
          reasons: ['违规或事件已经偏多，继续交易容易扩大偏差。'],
          tone: 'danger' as const,
        }
      : filterFailCount >= 2 || abnormalCount >= 2
        ? {
            action: '可以观察，但应显著降频，只做最清晰机会。',
            label: '降频观察',
            reasons: ['过滤失败或异常场景偏多，市场条件不理想。'],
            tone: 'warning' as const,
          }
        : {
            action: '可继续执行，但保持按计划筛选，不追单。',
            label: '可继续执行',
            reasons: ['当前纪律偏差可控，尚未出现明显停手信号。'],
            tone: 'success' as const,
          }

  const risk =
    pnlHkd < 0 || unfollowedCount >= 2 || violationCount >= 1
      ? {
          action: '重点盯住偏离计划、连续亏损和规则破坏。',
          label: '风险抬升',
          reasons: [
            pnlHkd < 0 ? '当前总盈亏为负，注意避免想扳回来的冲动。': '',
            unfollowedCount >= 2 ? '多笔交易未按计划执行。': '',
            violationCount >= 1 ? '已经出现规则违规。': '',
          ].filter(Boolean),
          tone: violationCount >= 1 ? 'danger' as const : 'warning' as const,
        }
      : {
          action: '节奏暂时可控，但仍要坚持过滤与时段纪律。',
          label: '风险可控',
          reasons: ['当前未看到明显失控征兆。'],
          tone: 'success' as const,
        }

  const todos = [
    trades.length === 0 ? '若要开仓，先确认是否符合当前主计划与过滤条件。': '',
    trades.length > 0 ? '补齐每笔交易的情绪、过滤、异常场景和备注字段。': '',
    eventCount === 0 ? '若出现情绪波动、违规或停手动作，及时登记纪律事件。': '',
    filterFailCount > 0 ? '回看过滤失败的交易，确认是否还在重复做低质量机会。': '',
    violationCount > 0 ? '先处理违规原因，再决定是否继续交易。': '',
  ].filter(Boolean)

  return { execution, risk, todos }
}
