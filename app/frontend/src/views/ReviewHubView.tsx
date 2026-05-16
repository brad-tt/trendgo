import { startTransition, useEffect, useState } from 'react'

import { Badge } from '../components/ui/Badge'
import { MetricCard } from '../components/MetricCard'
import { ReadonlyDayDetail } from '../components/review/ReadonlyDayDetail'
import type { AppState, DailyRecord, ReviewHubDayRow, ReviewHubStats } from '../types'
import { apiClient } from '../utils/apiClient'
import { displayValue, formatTradeDate } from '../utils/display'
import { formatHkdSummaryAmount } from '../utils/money'

export function ReviewHubView({ embedded = false }: { embedded?: boolean }) {
  const [stats, setStats] = useState<ReviewHubStats | null>(null)
  const [rows, setRows] = useState<ReviewHubDayRow[]>([])
  const [window, setWindow] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedRecordPath, setSelectedRecordPath] = useState('')
  const [selectedDay, setSelectedDay] = useState<DailyRecord | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')
  const [currentMarket, setCurrentMarket] = useState<'HK' | 'US'>('HK')

  useEffect(() => {
    let active = true

    async function load() {
      try {
        setLoading(true)
        const state = await apiClient.get<AppState>('/api/state')
        if (!active) return
        setWindow(state.reviewHubWindow)
        setCurrentMarket(state.currentMarket === 'US' ? 'US' : 'HK')
        const [nextStats, nextRows] = await Promise.all([
          apiClient.get<ReviewHubStats>(
            `/api/review-hub/stats?window=${state.reviewHubWindow}&sampleFilter=all`,
          ),
          apiClient.get<ReviewHubDayRow[]>(
            `/api/review-hub/days?window=${state.reviewHubWindow}&sampleFilter=all`,
          ),
        ])
        if (!active) return
        setStats(nextStats)
        setRows(nextRows)
      } catch (err) {
        if (!active) return
        setError(err instanceof Error ? err.message : '加载复盘中心失败。')
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [])

  const applyFilters = async (nextWindow: string) => {
    setError('')
    setLoading(true)
    setSelectedRecordPath('')
    setSelectedDay(null)
    setDetailError('')
    try {
      await apiClient.put('/api/state/review-hub', {
        sampleFilter: 'all',
        window: nextWindow,
      })
      const [nextStats, nextRows] = await Promise.all([
        apiClient.get<ReviewHubStats>(
          `/api/review-hub/stats?window=${nextWindow}&sampleFilter=all`,
        ),
        apiClient.get<ReviewHubDayRow[]>(
          `/api/review-hub/days?window=${nextWindow}&sampleFilter=all`,
        ),
      ])
      startTransition(() => {
        setStats(nextStats)
        setRows(nextRows)
        setWindow(nextWindow)
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : '刷新复盘中心失败。')
    } finally {
      setLoading(false)
    }
  }

  const loadDayDetail = async (row: ReviewHubDayRow) => {
    setSelectedRecordPath(row.path)
    setDetailError('')
    setDetailLoading(true)
    try {
      const day = await apiClient.get<DailyRecord>(`/api/records?path=${encodeURIComponent(row.path)}`)
      startTransition(() => {
        setSelectedDay(day)
      })
    } catch (err) {
      setSelectedDay(null)
      setDetailError(err instanceof Error ? err.message : '加载历史复盘失败。')
    } finally {
      setDetailLoading(false)
    }
  }

  return (
    <section className="space-y-5">
      <article className={embedded ? 'tt-card p-6' : 'tt-card tt-hero p-6'}>
        <div className="relative z-10 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className={embedded ? 'tt-heading-page' : 'tt-heading-page text-3xl'}>
              {embedded ? '历史统计与只读复盘' : '历史交易统计与复盘信号'}
            </h2>
          </div>
          <div className="flex flex-wrap gap-3">
            <Badge label={currentMarket === 'US' ? '当前：美股工作台' : '当前：港股工作台'} />
            <label className="rounded-full border border-toptrader-brand/20 bg-toptrader-panel/86 px-3 py-2 text-sm font-semibold text-toptrader-muted shadow-sm">
              <span className="mr-2">范围</span>
              <select
                className="bg-transparent outline-none"
                onChange={(event) => void applyFilters(event.target.value)}
                value={window}
              >
                <option value="5">近 5 日</option>
                <option value="10">近 10 日</option>
                <option value="all">全部</option>
              </select>
            </label>
          </div>
        </div>

        <div className="relative z-10 mt-4 rounded-2xl border border-toptrader-line bg-toptrader-panel/78 p-4 shadow-sm">
          <div className="flex flex-wrap gap-2">
            <InfoPill label={`范围：${window === 'all' ? '全部交易日' : `近 ${window} 日`}`} />
            <InfoPill label="历史记录只读" tone="accent" />
            <InfoPill label="总盈亏统一折算港币" tone="neutral" />
          </div>
        </div>

        <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <MetricCard accent label="交易天数" value={stats?.dayCount ?? '--'} />
          <MetricCard
            helper="美股按 7.8 折算"
            label="总盈亏"
            value={formatHkdSummaryAmount(stats?.totalPnl)}
          />
          <MetricCard label="总交易数" value={stats?.tradeCount ?? '--'} />
          <MetricCard label="违规次数" value={stats?.violationCount ?? '--'} />
          <MetricCard label="有交易日" value={stats?.tradeDayCount ?? '--'} />
          <MetricCard
            label="按计划率"
            value={
              stats?.planFollowRate === null || stats?.planFollowRate === undefined
                ? '--'
                : `${stats.planFollowRate.toFixed(1)}%`
            }
          />
          <MetricCard
            label="赢 / 亏 / 平"
            value={stats ? `${stats.winCount} / ${stats.lossCount} / ${stats.breakevenCount}` : '--'}
          />
          <MetricCard label="冲动交易日" value={stats?.impulsiveDays ?? '--'} />
          <MetricCard label="止损失守日" value={stats?.stopLossDays ?? '--'} />
          <MetricCard label="过度交易日" value={stats?.overtradeDays ?? '--'} />
        </div>
      </article>

      <article className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_320px]">
        <div className="tt-card p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-display text-xl font-bold text-toptrader-accent">交易日明细</h3>
            </div>
            <span className="rounded-full bg-teal-50 px-3 py-2 text-xs font-bold text-teal-700">
              {rows.length} 个交易日
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="tt-table min-w-full text-left text-sm">
              <thead>
                <tr>
                  <th className="px-3 py-3 font-medium">日期</th>
                  <th className="px-3 py-3 font-medium">模式</th>
                  <th className="px-3 py-3 font-medium">交易</th>
                  <th className="px-3 py-3 font-medium">盈亏(HKD)</th>
                  <th className="px-3 py-3 font-medium">状态</th>
                  <th className="px-3 py-3 font-medium">查看</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    className={[
                      'cursor-pointer transition',
                      selectedRecordPath === row.path ? 'bg-teal-50/80' : 'hover:bg-sky-50/55',
                    ].join(' ')}
                    key={row.path}
                    onClick={() => void loadDayDetail(row)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        void loadDayDetail(row)
                      }
                    }}
                    role="button"
                    tabIndex={0}
                  >
                    <td className="px-3 py-4 font-medium text-toptrader-accent">{formatTradeDate(row.tradeDate)}</td>
                    <td className="px-3 py-4 text-toptrader-muted">
                      {displayValue(row.market === 'US' ? 'us_stock_options' : row.tradingMode)}
                    </td>
                    <td className="px-3 py-4 text-toptrader-accent">{row.tradeCount}</td>
                    <td className="px-3 py-4 text-toptrader-accent">{formatHkdSummaryAmount(row.pnlValue)}</td>
                    <td className="px-3 py-4 text-xs text-toptrader-muted">
                      <div className="flex flex-wrap gap-1.5">
                        <Badge label={row.isCurrent ? '当日交易日' : '历史只读'} />
                        {row.impulsiveFlag ? <Badge label="冲动交易" tone="warning" /> : null}
                        {row.overtradeFlag ? <Badge label="过度交易" tone="warning" /> : null}
                        {row.stopLossFlag ? <Badge label="止损失守" tone="danger" /> : null}
                      </div>
                    </td>
                    <td className="px-3 py-4">
                      <span className="rounded-full border border-toptrader-brand/20 bg-toptrader-panel px-3 py-1.5 text-xs font-bold text-toptrader-brand shadow-sm">
                        查看复盘
                      </span>
                    </td>
                  </tr>
                ))}
                {!rows.length ? (
                  <tr>
                    <td className="px-3 py-8 text-center text-sm text-toptrader-muted" colSpan={6}>
                      当前筛选条件下没有匹配的交易日。
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
          <ReadonlyDayDetail
            day={selectedDay}
            error={detailError}
            loading={detailLoading}
            selectedRecordPath={selectedRecordPath}
          />
          {error ? (
            <p className="mt-4 rounded-2xl border border-toptrader-rose/30 bg-toptrader-rose/10 px-4 py-3 text-sm text-toptrader-rose">
              {error}
            </p>
          ) : null}
        </div>

        <aside className="tt-card p-6 xl:sticky xl:top-28 xl:self-start">
          <div className="space-y-5">
            <SignalBlock
              items={stats?.recentIssues.map((item) => `${formatTradeDate(item.tradeDate)}：${item.note}`) ?? []}
              title="最近主要问题"
            />
          </div>
          {loading ? (
            <p className="mt-5 text-sm text-toptrader-muted">正在刷新筛选结果…</p>
          ) : null}
        </aside>
      </article>
    </section>
  )
}

function InfoPill({
  label,
  tone = 'neutral',
}: {
  label: string
  tone?: 'accent' | 'neutral' | 'warning'
}) {
  const toneClass =
    tone === 'accent'
      ? 'border-toptrader-brand/20 bg-toptrader-brand/10 text-toptrader-brand'
      : tone === 'warning'
        ? 'border-amber-500/30 bg-amber-500/10 text-amber-400'
        : 'border-toptrader-line bg-toptrader-panel text-toptrader-muted'

  return <span className={['rounded-full border px-3 py-1 text-sm font-medium', toneClass].join(' ')}>{label}</span>
}

function SignalBlock({ items, title }: { items: string[]; title: string }) {
  return (
    <div>
      <h3 className="font-display text-lg font-semibold tracking-tight text-toptrader-accent">
        {title}
      </h3>
      {items.length ? (
        <ul className="mt-3 space-y-2 text-sm leading-6 text-toptrader-muted">
          {items.map((item) => (
            <li key={item} className="rounded-2xl border border-toptrader-line bg-toptrader-panel px-4 py-3 shadow-sm">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-toptrader-muted">暂无数据。</p>
      )}
    </div>
  )
}
