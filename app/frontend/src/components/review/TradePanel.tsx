import { useMemo, useState } from 'react'

import type { DailyRecord, DayActionResponse } from '../../types'
import { apiClient } from '../../utils/apiClient'
import { effectiveTradingMode } from '../../utils/trading'
import { formatHkdSummaryAmount, sumTradesPnlHkd } from '../../utils/money'
import { SummaryCard } from './reviewUi'
import { TradeCard } from './TradeCard'
import { TradeEditorDrawer } from './TradeEditorDrawer'
import type { TradeWritePayload } from './tradeForm'

interface TradePanelProps {
  day: DailyRecord
  onDayChange: (updatedDay: DailyRecord) => void
}

export function TradePanel({ day, onDayChange }: TradePanelProps) {
  const [expandedTradeId, setExpandedTradeId] = useState<string | null>(null)
  const [editingTradeId, setEditingTradeId] = useState<string | null>(null)
  const [closingTradeId, setClosingTradeId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const mode = effectiveTradingMode(day)
  const tradeSummary = useMemo(
    () => ({
      count: day.trades.length,
      pnlHkd: sumTradesPnlHkd(day.trades),
    }),
    [day.trades],
  )
  const editingTrade = day.trades.find((trade) => trade.tradeId === editingTradeId)
  const closingTrade = day.trades.find((trade) => trade.tradeId === closingTradeId)
  const dayKey = {
    market: day.base.market,
    tradeDate: day.base.tradeDate,
  }

  const createTrade = async (payload: TradeWritePayload) => {
    const response = await apiClient.post<DayActionResponse>('/api/day-records/trades', {
      ...dayKey,
      ...payload,
    })
    onDayChange(response.day)
  }

  const updateTrade = async (payload: TradeWritePayload) => {
    if (!editingTradeId) return
    const response = await apiClient.put<DayActionResponse>(
      `/api/day-records/trades/${editingTradeId}?tradeDate=${encodeURIComponent(dayKey.tradeDate)}&market=${encodeURIComponent(dayKey.market)}`,
      payload,
    )
    onDayChange(response.day)
  }

  const closeTrade = async (payload: TradeWritePayload) => {
    if (!closingTradeId) return
    const response = await apiClient.put<DayActionResponse>(
      `/api/day-records/trades/${closingTradeId}?tradeDate=${encodeURIComponent(dayKey.tradeDate)}&market=${encodeURIComponent(dayKey.market)}`,
      payload,
    )
    onDayChange(response.day)
  }

  const deleteTrade = async (tradeId: string) => {
    if (!window.confirm(`确认删除交易 ${tradeId} 吗？`)) return
    const response = await apiClient.delete<DayActionResponse>(
      `/api/day-records/trades/${tradeId}?tradeDate=${encodeURIComponent(dayKey.tradeDate)}&market=${encodeURIComponent(dayKey.market)}`,
    )
    onDayChange(response.day)
  }

  return (
    <>
      <section className="tt-bento p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2.5">
          <div>
            <h2 className="tt-heading-page">交易流水</h2>
          </div>
          {day.isCurrent && day.preMarket.tradingToday ? (
            <button className="tt-primary px-3 py-2 text-xs font-bold" onClick={() => setCreating(true)} type="button">
              记录开仓
            </button>
          ) : null}
        </div>
        {!day.preMarket.tradingToday ? (
          <div className="mb-3 rounded-xl border border-sky-500/25 bg-sky-500/8 px-4 py-3 text-[12px] leading-5 text-toptrader-accent">
            今天已设为不交易。盘中页默认按空仓日处理，不鼓励新增交易，只保留必要的纪律事实或等待记录。
          </div>
        ) : null}
        <div className="mb-3 grid gap-3 sm:grid-cols-3">
          <SummaryCard label="交易数" value={tradeSummary.count} />
          <SummaryCard label="纪律事件" value={day.events.length} />
          <SummaryCard label="当前盈亏(HKD)" value={formatHkdSummaryAmount(tradeSummary.pnlHkd)} />
        </div>
        <div className="space-y-2.5">
          {day.trades.map((trade) => (
            <TradeCard
              key={trade.tradeId}
              isCurrent={day.isCurrent}
              isExpanded={expandedTradeId === trade.tradeId}
              onCloseTrade={setClosingTradeId}
              onDelete={deleteTrade}
              onEdit={setEditingTradeId}
              onToggleExpand={(tradeId) => setExpandedTradeId((current) => (current === tradeId ? null : tradeId))}
              trade={trade}
            />
          ))}
          {!day.trades.length ? (
            <div className="rounded-xl border border-toptrader-line bg-toptrader-panel px-4 py-6 text-center text-xs text-toptrader-muted">
              {day.preMarket.tradingToday ? '当前没有交易记录。' : '空仓日当前没有交易记录。'}
            </div>
          ) : null}
        </div>
      </section>

      <TradeEditorDrawer key={`create-${mode}`} isOpen={creating && day.preMarket.tradingToday} mode="create" onClose={() => setCreating(false)} onSubmit={createTrade} title="记录开仓" trade={undefined} tradingMode={mode} />
      <TradeEditorDrawer key={closingTrade ? `close-${closingTrade.tradeId}` : 'close-empty'} isOpen={Boolean(closingTrade)} mode="close" onClose={() => setClosingTradeId(null)} onSubmit={closeTrade} title={closingTrade ? `记录平仓 ${closingTrade.tradeId}` : '记录平仓'} trade={closingTrade} tradingMode={mode} />
      <TradeEditorDrawer key={editingTrade ? `edit-${editingTrade.tradeId}` : 'edit-empty'} isOpen={Boolean(editingTrade)} mode="edit" onClose={() => setEditingTradeId(null)} onSubmit={updateTrade} title={editingTrade ? `编辑 ${editingTrade.tradeId}` : '编辑交易'} trade={editingTrade} tradingMode={mode} />
    </>
  )
}
