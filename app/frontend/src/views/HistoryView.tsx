import { useEffect, useMemo, useState } from 'react'

import { ReviewHubView } from './ReviewHubView'
import { Badge } from '../components/ui/Badge'
import { MetaRow } from '../components/ui/MetaRow'
import { SummaryCard } from '../components/ui/SummaryCard'
import { useWorkspace } from '../contexts/WorkspaceContext'
import type { HistoryOverview } from '../types'
import { apiClient } from '../utils/apiClient'
import { formatTradeDate } from '../utils/display'
import { formatHkdSummaryAmount } from '../utils/money'

export function HistoryView() {
  const { state } = useWorkspace()
  const [overview, setOverview] = useState<HistoryOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function loadOverview() {
      try {
        setLoading(true)
        setError('')
        const nextOverview = await apiClient.get<HistoryOverview>('/api/history/overview')
        if (!active) return
        setOverview(nextOverview)
      } catch (err) {
        if (!active) return
        setError(err instanceof Error ? err.message : '加载历史总览失败。')
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadOverview()
    return () => {
      active = false
    }
  }, [])

  const stats = overview?.stats
  const days = overview?.days ?? []
  const historyState = useMemo(
    () =>
      buildHistoryState({
        closeoutSyncedDays: stats?.closeoutSyncedDays ?? 0,
        dayCount: stats?.dayCount ?? 0,
        impulsiveDays: stats?.impulsiveDays ?? 0,
        overtradeDays: stats?.overtradeDays ?? 0,
        recentIssueCount: stats?.recentIssues.length ?? 0,
        totalPnl: stats?.totalPnl ?? null,
        violationCount: stats?.violationCount ?? 0,
      }),
    [stats],
  )

  return (
    <section className="space-y-3">
      <div>
        <h2 className="tt-heading-page">历史复查</h2>
      </div>

      <section className="tt-bento-panel">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="tt-heading-card">历史驾驶舱</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge label={state?.currentMarket === 'US' ? '当前：美股工作台' : '当前：港股工作台'} />
            <Badge label={overview?.window === 'all' || !overview ? '全部交易日' : `近 ${overview.window} 日`} tone="success" />
            <Badge label={overview?.sampleFilter === 'all' || !overview ? '全部样本' : overview.sampleFilter} />
          </div>
        </div>
        {error ? <p className="mt-4 text-sm text-toptrader-rose">{error}</p> : null}
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <SummaryCard label="历史状态" value={historyState.label} helper={historyState.action} />
          <SummaryCard label="交易天数" value={stats?.dayCount ?? '--'} />
          <SummaryCard label="总盈亏(HKD)" value={formatHkdSummaryAmount(stats?.totalPnl)} />
          <SummaryCard label="已载入交易日" value={days.length} />
        </div>
        <div className="mt-4 grid gap-3 xl:grid-cols-3">
          <StatusPanel
            action={historyState.action}
            details={historyState.reasons}
            label={historyState.label}
            title="最近样本状态"
            tone={historyState.tone}
          />
          <ChecklistPanel
            items={[
              stats?.recentIssues.length ? '优先先看最近主要问题，确认是不是老问题在重复。' : '当前没有最近主要问题记录。',
              stats?.recentFixes.length ? '再看最近主要修正，判断有没有真正改善。' : '当前没有最近主要修正记录。',
              stats?.recentNoTradeNotes.length ? '如果最近空仓日偏多，要看空仓说明是否真实。' : '最近没有空仓说明记录。',
            ]}
            title="建议查看顺序"
          />
          <ChecklistPanel
            items={[
              stats?.topActivePlans.length ? `高频计划：${stats.topActivePlans.map((item) => `${item.label}(${item.count})`).join('，')}` : '暂无高频计划统计。',
              stats?.topActiveSetups.length ? `高频主练形态：${stats.topActiveSetups.map((item) => `${item.label}(${item.count})`).join('，')}` : '暂无高频主练形态统计。',
              stats?.topSetups.length ? `高频实际形态：${stats.topSetups.map((item) => `${item.label}(${item.count})`).join('，')}` : '暂无高频实际形态统计。',
            ]}
            title="模式提醒"
          />
        </div>
      </section>

      <section className="tt-bento-grid">
        <div className="col-span-12 xl:col-span-8 space-y-3">
          <section className="tt-bento-panel">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="tt-heading-card">历史模式总览</h3>
              </div>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <SummaryCard label="有交易日" value={stats?.tradeDayCount ?? '--'} />
              <SummaryCard label="总交易数" value={stats?.tradeCount ?? '--'} />
              <SummaryCard label="日均盈亏(HKD)" value={formatHkdSummaryAmount(stats?.avgDailyPnl)} />
              <SummaryCard label="违规次数" value={stats?.violationCount ?? '--'} />
              <SummaryCard label="复盘完成天数" value={stats?.reviewDoneDays ?? '--'} />
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <MetaRow label="按计划执行" value={stats ? `${stats.followedYes} / ${stats.followedTotal}` : '--'} />
              <MetaRow label="按计划率" value={stats?.planFollowRate === null || stats?.planFollowRate === undefined ? '--' : `${stats.planFollowRate.toFixed(1)}%`} />
              <MetaRow label="盈利 / 亏损 / 持平" value={stats ? `${stats.winCount} / ${stats.lossCount} / ${stats.breakevenCount}` : '--'} />
              <MetaRow label="异常场景交易" value={String(stats?.abnormalTradeCount ?? '--')} />
              <MetaRow label="过滤未通过" value={String(stats?.certificateFilterFailCount ?? '--')} />
              <MetaRow label="开盘 30 分钟交易" value={String(stats?.opening30TradeCount ?? '--')} />
              <MetaRow label="冲动交易日" value={String(stats?.impulsiveDays ?? '--')} />
              <MetaRow label="止损失守日" value={String(stats?.stopLossDays ?? '--')} />
              <MetaRow label="过度交易日" value={String(stats?.overtradeDays ?? '--')} />
              <MetaRow label="空仓日" value={String(stats?.noTradeDayCount ?? '--')} />
              <MetaRow label="验证完成天数" value={String(stats?.validationDoneDays ?? '--')} />
              <MetaRow label="归档已同步天数" value={String(stats?.closeoutSyncedDays ?? '--')} />
            </div>
          </section>

          <section className="tt-bento-panel">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="tt-heading-card">问题与修正线索</h3>
              </div>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <MetaRow label="最近主要问题" value={stats?.recentIssues.map((item) => `${formatTradeDate(item.tradeDate)}：${item.note}`).join('；') || '--'} />
              <MetaRow label="最近主要修正" value={stats?.recentFixes.map((item) => `${formatTradeDate(item.tradeDate)}：${item.note}`).join('；') || '--'} />
              <MetaRow label="最近空仓说明" value={stats?.recentNoTradeNotes.map((item) => `${formatTradeDate(item.tradeDate)}：${item.note}`).join('；') || '--'} />
              <MetaRow label="高频计划" value={stats?.topActivePlans.map((item) => `${item.label}(${item.count})`).join('，') || '--'} />
              <MetaRow label="高频主练形态" value={stats?.topActiveSetups.map((item) => `${item.label}(${item.count})`).join('，') || '--'} />
              <MetaRow label="高频实际形态" value={stats?.topSetups.map((item) => `${item.label}(${item.count})`).join('，') || '--'} />
            </div>
          </section>
        </div>

        <div className="col-span-12 xl:col-span-4 space-y-3">
          <section className="tt-bento-panel">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="tt-heading-card">使用说明</h3>
              </div>
            </div>
            <div className="mt-4 grid gap-3">
              <MetaRow label="当前载入状态" value={loading ? '正在刷新历史总览' : '已完成总览载入'} />
            </div>
          </section>
        </div>
      </section>

      <ReviewHubView />
    </section>
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
    <div className="rounded-xl border border-toptrader-line bg-toptrader-panel px-3 py-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-toptrader-accent">{title}</div>
          <div className="mt-1 text-xs text-toptrader-muted">{action || '--'}</div>
        </div>
        <Badge label={label || '--'} tone={tone} />
      </div>
      <div className="mt-3 space-y-2">
        {details.length ? details.map((detail) => <div key={detail} className="rounded-lg bg-toptrader-soft/55 px-2.5 py-2 text-xs leading-5 text-toptrader-ink">{detail}</div>) : <div className="text-xs text-toptrader-muted">暂无额外信号。</div>}
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
    <div className="rounded-xl border border-toptrader-line bg-toptrader-panel px-3 py-3">
      <div className="text-sm font-semibold text-toptrader-accent">{title}</div>
      <div className="mt-3 space-y-2">
        {items.length ? items.map((item) => <div key={item} className="rounded-lg bg-toptrader-soft/55 px-2.5 py-2 text-xs leading-5 text-toptrader-ink">{item}</div>) : <div className="text-xs text-toptrader-muted">当前无新增提示。</div>}
      </div>
    </div>
  )
}

function buildHistoryState({
  closeoutSyncedDays,
  dayCount,
  impulsiveDays,
  overtradeDays,
  recentIssueCount,
  totalPnl,
  violationCount,
}: {
  closeoutSyncedDays: number
  dayCount: number
  impulsiveDays: number
  overtradeDays: number
  recentIssueCount: number
  totalPnl: number | null
  violationCount: number
}) {
  if (dayCount > 0 && closeoutSyncedDays === dayCount && violationCount === 0 && impulsiveDays === 0 && overtradeDays === 0) {
    return {
      action: '最近样本相对干净，可以重点看高频形态和有效动作。',
      label: '样本较稳定',
      reasons: ['闭环同步完整，纪律问题较少。'],
      tone: 'success' as const,
    }
  }
  if (violationCount > 0 || impulsiveDays > 0 || overtradeDays > 0 || recentIssueCount > 0) {
    return {
      action: '优先沿着最近问题和纪律风险往下看，找重复模式。',
      label: '问题待复查',
      reasons: [
        violationCount > 0 ? `累计违规次数 ${violationCount}。` : '',
        impulsiveDays > 0 ? `冲动交易日 ${impulsiveDays}。` : '',
        overtradeDays > 0 ? `过度交易日 ${overtradeDays}。` : '',
        recentIssueCount > 0 ? `最近主要问题记录 ${recentIssueCount} 条。` : '',
      ].filter(Boolean),
      tone: 'warning' as const,
    }
  }
  return {
    action: totalPnl !== null && totalPnl < 0 ? '先看亏损样本和问题模式，再看高频计划。': '先从最近样本切入，逐步确认模式。',
    label: '常规复查',
    reasons: ['当前历史样本没有明显失控，但仍需要按顺序回看。'],
    tone: 'neutral' as const,
  }
}
