import { useMemo, useState } from 'react'

import { CloseoutPanel } from '../components/review/CloseoutPanel'
import { ReviewForm } from '../components/review/ReviewForm'
import { ValidationPanel } from '../components/review/ValidationPanel'
import { Toast, type ToastState } from '../components/Toast'
import { Badge } from '../components/ui/Badge'
import { SummaryCard } from '../components/ui/SummaryCard'
import { useWorkspaceData } from '../hooks/useWorkspaceData'
import type { CloseoutPayload, DayActionResponse } from '../types'
import { displayValue, formatTradeDate } from '../utils/display'
import { apiClient } from '../utils/apiClient'
import { formatHkdSummaryAmount, formatNumber, sumTradesPnlHkd, winRateText } from '../utils/money'

export function PostmarketView() {
  const { day, error, loading, refresh, setDay } = useWorkspaceData()
  const [toast, setToast] = useState<ToastState | null>(null)

  const reviewSnapshot = useMemo(() => {
    const trades = day?.trades ?? []
    return {
      eventCount: day?.events.length ?? 0,
      pnlHkd: sumTradesPnlHkd(trades),
      pnlText: formatNumber(sumTradesPnlHkd(trades)),
      tradeCount: trades.length,
      winRate: winRateText(trades),
    }
  }, [day])

  const syncReviewNumbers = async () => {
    if (!day) return
    try {
      const response = await apiClient.post<DayActionResponse>('/api/day-records/review/sync-numbers', {
        afterAction: '',
        market: day.base.market,
        tradeDate: day.base.tradeDate,
      })
      setDay(response.day)
      setToast({ message: response.message, tone: 'success' })
      await refresh()
    } catch (err) {
      setToast({ message: err instanceof Error ? err.message : '同步复盘数字失败。', tone: 'error' })
    }
  }

  const saveReviewAndGenerateCloseout = async (updatedDay: typeof day) => {
    if (!updatedDay) return
    const nextCloseout = await apiClient.post<CloseoutPayload>('/api/day-records/closeout', {
      market: updatedDay.base.market,
      regenerate: true,
      tradeDate: updatedDay.base.tradeDate,
    })
    setDay({
      ...updatedDay,
      closeout: nextCloseout,
    })
    await refresh()
    setToast({ message: '复盘已保存，归档草稿已更新。', tone: 'success' })
  }

  const refreshCloseout = async (updatedCloseout: CloseoutPayload) => {
    if (!day) return
    try {
      const nextCloseout = updatedCloseout.stale
        ? await apiClient.post<CloseoutPayload>('/api/day-records/closeout', {
            market: day.base.market,
            regenerate: true,
            tradeDate: day.base.tradeDate,
          })
        : await apiClient.get<CloseoutPayload>(
            `/api/day-records/closeout?tradeDate=${encodeURIComponent(day.base.tradeDate)}&market=${encodeURIComponent(day.base.market)}`,
          )
      setDay({
        ...day,
        closeout: nextCloseout,
      })
      await refresh()
      setToast({
        message: updatedCloseout.stale ? '归档草稿已重新生成。' : '已刷新归档草稿预览。',
        tone: 'success',
      })
    } catch (error) {
      setToast({ message: error instanceof Error ? error.message : '更新归档草稿失败。', tone: 'error' })
    }
  }

  const saveValidationAndGenerateCloseout = async (updatedDay: typeof day) => {
    if (!updatedDay) return
    try {
      setDay(updatedDay)
      const nextCloseout = await apiClient.post<CloseoutPayload>('/api/day-records/closeout', {
        market: updatedDay.base.market,
        regenerate: true,
        tradeDate: updatedDay.base.tradeDate,
      })
      setDay({
        ...updatedDay,
        closeout: nextCloseout,
      })
      await refresh()
      setToast({ message: '验证已保存，归档草稿已更新。', tone: 'success' })
    } catch (error) {
      setToast({ message: error instanceof Error ? error.message : '更新归档草稿失败。', tone: 'error' })
    }
  }

  if (loading && !day) {
    return <Placeholder text="正在加载盘后复盘视图…" />
  }

  if (!day) {
    return <Placeholder text={error || '当前没有可编辑交易日。'} />
  }

  return (
    <>
      <Toast onClear={() => setToast(null)} toast={toast} />
      <section className="space-y-3">
        <div>
          <h2 className="tt-heading-page">盘后闭环</h2>
        </div>

        {!day.preMarket.tradingToday ? (
          <section className="tt-bento-panel accent col-span-12 rounded-[20px] border-sky-500/30 bg-gradient-to-r from-toptrader-panel via-sky-900/10 to-toptrader-panel p-4">
            <div className="text-xs font-black uppercase tracking-[0.18em] text-toptrader-sky">空仓日复盘</div>
            <p className="mt-2 text-xs leading-5 text-toptrader-muted">
              今天盘前已明确不交易。这里只写空仓原因、等待纪律和明天只改的一件事。
            </p>
          </section>
        ) : null}

        <section className="tt-bento-panel">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="tt-heading-card">盘后事实条</h3>
              <p className="mt-1 text-xs leading-5 text-toptrader-muted">
                先看事实，再回答 4 个问题。把盘后复盘控制在 3 分钟内完成。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge label={formatTradeDate(day.base.tradeDate)} tone="success" />
              <Badge label={displayValue(day.base.market)} />
              <Badge label={displayValue(day.workbench.tradingMode)} />
              {day.isCurrent ? (
                <button className="tt-secondary px-4 py-2.5 text-sm font-bold" onClick={() => void syncReviewNumbers()} type="button">
                  同步数字
                </button>
              ) : null}
            </div>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <SummaryCard label="当日盈亏(HKD)" value={formatHkdSummaryAmount(reviewSnapshot.pnlHkd)} />
            <SummaryCard label="交易数" value={reviewSnapshot.tradeCount} />
            <SummaryCard label="胜率" value={reviewSnapshot.winRate} />
            <SummaryCard label="纪律事件数" value={reviewSnapshot.eventCount} />
          </div>
        </section>

        <ReviewForm
          isCurrent={day.isCurrent}
          market={day.base.market}
          onSave={async (updatedDay) => {
            setDay(updatedDay)
            setToast({ message: '复盘已保存。', tone: 'success' })
            await refresh()
          }}
          onSaveAndGenerateCloseout={saveReviewAndGenerateCloseout}
          review={{
            ...day.review,
            pnl: reviewSnapshot.pnlText,
            tradeCount: reviewSnapshot.tradeCount,
            winRate: reviewSnapshot.winRate === '--' ? '' : reviewSnapshot.winRate,
          }}
          tradeDate={day.base.tradeDate}
        />

        <div className="tt-bento-grid">
          <div className="col-span-12 xl:col-span-7 space-y-3">
            <ValidationPanel
              isCurrent={day.isCurrent}
              market={day.base.market}
              onSave={async (updatedDay) => {
                setDay(updatedDay)
                setToast({ message: '验证已保存。', tone: 'success' })
                await refresh()
              }}
              onSaveAndGenerateCloseout={saveValidationAndGenerateCloseout}
              tradingToday={day.preMarket.tradingToday}
              tradeDate={day.base.tradeDate}
              validation={day.validation}
            />
          </div>

          <div className="col-span-12 xl:col-span-5 space-y-3">
            <CloseoutPanel
              closeout={day.closeout}
              isCurrent={day.isCurrent}
              onGenerated={refreshCloseout}
              tradeDate={day.base.tradeDate}
            />
          </div>
        </div>

        <section className="tt-bento-panel">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="tt-heading-card">当日交易流水</h3>
              <p className="mt-1 text-xs leading-5 text-toptrader-muted">
                复盘时直接看每一笔交易的关键信息，不用切去别的页面。
              </p>
            </div>
          </div>
          {day.trades.length ? (
            <div className="mt-4 overflow-x-auto">
              <table className="tt-table min-w-full text-left text-[12px]">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>代码</th>
                    <th>方向</th>
                    <th>形态</th>
                    <th>仓位</th>
                    <th>入场</th>
                    <th>出场</th>
                    <th>盈亏</th>
                    <th>计划</th>
                    <th>异常</th>
                  </tr>
                </thead>
                <tbody>
                  {day.trades.map((trade) => (
                    <tr key={trade.tradeId}>
                      <td>{trade.tradeTime || '--'}</td>
                      <td>{trade.instrumentCode || '--'}</td>
                      <td>{displayValue(trade.direction)}</td>
                      <td>{displayValue(trade.setupType)}</td>
                      <td>{trade.positionSize || '--'}</td>
                      <td>{trade.entryPrice ?? '--'}</td>
                      <td>{trade.exitPrice ?? '--'}</td>
                      <td>{trade.pnlAmount === null || trade.pnlAmount === undefined ? '--' : formatHkdSummaryAmount(trade.pnlAmountHkd ?? trade.pnlAmount)}</td>
                      <td>{trade.followedPlan ? '按计划' : '偏离'}</td>
                      <td>{trade.abnormalScenario && trade.abnormalScenario !== 'none' ? displayValue(trade.abnormalScenario) : '--'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="mt-4 rounded-xl border border-dashed border-toptrader-line bg-toptrader-panel/70 px-4 py-5 text-sm text-toptrader-muted">
              今天没有交易流水。
            </div>
          )}
        </section>
      </section>
    </>
  )
}

function Placeholder({ text }: { text: string }) {
  return <section className="tt-card p-6 text-sm text-toptrader-muted">{text}</section>
}
