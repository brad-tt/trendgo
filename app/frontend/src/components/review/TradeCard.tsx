import { displayValue } from '../../utils/display'
import { formatTradePnl } from '../../utils/money'
import type { Trade } from '../../types'
import { Badge } from '../ui/Badge'
import { formatTradeTimeRange, pnlToneClass } from './reviewUtils'

interface TradeCardProps {
  trade: Trade
  isExpanded: boolean
  isCurrent: boolean
  onCloseTrade: (tradeId: string) => void
  onToggleExpand: (tradeId: string) => void
  onEdit: (tradeId: string) => void
  onDelete: (tradeId: string) => Promise<void>
}

export function TradeCard({
  trade,
  isExpanded,
  isCurrent,
  onCloseTrade,
  onToggleExpand,
  onEdit,
  onDelete,
}: TradeCardProps) {
  const pnl = formatTradePnl(trade)
  const isOpenTrade = !trade.exitTime && trade.exitPrice === null
  const hasFilterFail = trade.certificateFilterPassed === false
  const hasAbnormal = trade.abnormalScenario && trade.abnormalScenario !== 'none'
  const summaryBits = [
    trade.instrumentCode || '--',
    displayValue(trade.direction),
    displayValue(trade.setupType),
  ]

  return (
    <div className="rounded-2xl border border-toptrader-line bg-toptrader-panel shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3 px-4 py-3.5">
        <div className="min-w-0 flex-1">
          <button className="text-left" onClick={() => onToggleExpand(trade.tradeId)} type="button">
            <div className="flex flex-wrap items-center gap-2">
              <div className="font-medium text-toptrader-accent">{trade.tradeId}</div>
              {isOpenTrade ? <Badge label="未平仓" tone="warning" /> : null}
              {trade.ruleViolation ? <Badge label="违规" tone="danger" /> : null}
              {hasFilterFail ? <Badge label="过滤失败" tone="warning" /> : null}
              {hasAbnormal ? <Badge label={displayValue(trade.abnormalScenario)} tone="warning" /> : null}
            </div>
            <div className="mt-1 text-[11px] text-toptrader-muted">{formatTradeTimeRange(trade)}</div>
            <div className="mt-1.5 flex flex-wrap gap-1.5 text-[11px] text-toptrader-muted">
              {summaryBits.map((bit) => (
                <span key={bit} className="rounded-full border border-toptrader-line bg-toptrader-soft/45 px-2 py-0.5 leading-4">
                  {bit}
                </span>
              ))}
            </div>
          </button>
        </div>
        <div className="text-right">
          <div className={['text-lg font-bold', pnlToneClass(trade.pnlAmount)].join(' ')}>{pnl.primary}</div>
          <div className="mt-0.5 text-[11px] text-toptrader-muted">{displayValue(trade.certificateSide)} / 仓位 {trade.positionSize || '--'}</div>
        </div>
      </div>

      {isExpanded ? (
        <div className="border-t border-toptrader-line px-4 py-3.5 text-sm text-toptrader-muted">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-2">
              <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-toptrader-muted">入场逻辑</div>
              <div className="rounded-xl border border-toptrader-line bg-toptrader-soft/35 px-3 py-3 leading-6 text-toptrader-ink">
                {trade.entryReason || '未填写入场说明'}
              </div>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <FactChip label="标的" value={trade.instrumentCode || '--'} />
              <FactChip label="仓位" value={trade.positionSize || '--'} />
              <FactChip label="是否按计划" value={trade.followedPlan ? '是' : '否'} />
              <FactChip label="过滤通过" value={trade.certificateFilterPassed === null ? '--' : trade.certificateFilterPassed ? '是' : '否'} />
              <FactChip label="盘前情绪" value={displayValue(trade.preTradeEmotion)} />
              <FactChip label="盘中情绪" value={displayValue(trade.emotionState)} />
            </div>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <FactChip label="异常场景" value={displayValue(trade.abnormalScenario)} />
            <FactChip label="复盘备注" value={trade.reviewNote || '--'} />
          </div>
          {isCurrent ? (
            <div className="mt-3 flex gap-2">
              {isOpenTrade ? (
                <button className="tt-primary px-3 py-2 text-xs font-bold" onClick={() => onCloseTrade(trade.tradeId)} type="button">
                  记录平仓
                </button>
              ) : null}
              <button className="tt-secondary px-3 py-2 text-xs font-bold" onClick={() => onEdit(trade.tradeId)} type="button">
                编辑
              </button>
              <button className="rounded-lg border border-rose-200 bg-white px-3 py-2 text-xs font-bold text-rose-700 transition hover:bg-rose-50" onClick={() => void onDelete(trade.tradeId)} type="button">
                删除
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

function FactChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-toptrader-line bg-toptrader-soft/35 px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-toptrader-muted">{label}</div>
      <div className="mt-0.5 text-[12px] leading-5 text-toptrader-accent">{value}</div>
    </div>
  )
}
