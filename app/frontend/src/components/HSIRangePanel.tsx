import { useEffect, useState } from 'react'

import type { HSIRangeState } from '../types'
import { apiClient } from '../utils/apiClient'

function fmtNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  return new Intl.NumberFormat('zh-CN', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value)
}

function fmtPct(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  return `${fmtNumber(value)}%`
}

function fmtPts(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(value)} 点`
}

export function HSIRangePanel() {
  const [state, setState] = useState<HSIRangeState | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function load() {
      try {
        setLoading(true)
        setError('')
        const next = await apiClient.get<HSIRangeState>('/api/market/hsi-range/state')
        if (!active) return
        setState(next)
        if (!next.ok) {
          setError(next.error || '恒指振幅参考暂时不可用。')
        }
      } catch (err) {
        if (!active) return
        setError(err instanceof Error ? err.message : '恒指振幅参考加载失败。')
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    const timer = window.setInterval(() => void load(), 15000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  const intraday = state?.intraday
  const status = state?.status
  const warnings = state?.warnings ?? []

  return (
    <section className="tt-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.18em] text-toptrader-sky">恒指参考</div>
          <h2 className="mt-2 tt-heading-page">
            日内振幅参考
          </h2>
          <p className="mt-1.5 max-w-3xl text-xs leading-5 text-toptrader-muted">
            用 200 个完整交易日的振幅分布，判断今天波动预算还剩多少。
          </p>
        </div>
        <div className="rounded-lg border border-toptrader-sky/20 bg-toptrader-sky/10 px-3 py-2 text-xs font-bold text-toptrader-sky">
          {loading ? '加载中…' : state?.snapshot?.updateTime ? `快照 ${state.snapshot.updateTime}` : '实时快照'}
        </div>
      </div>

      {error ? (
        <div className="mt-3 rounded-lg border border-amber-700/30 bg-amber-500/10 px-3 py-3 text-xs leading-5 text-amber-400">
          {error}
        </div>
      ) : null}

      {warnings.length ? (
        <div className="mt-3 space-y-1.5">
          {warnings.map((warning) => (
            <div key={warning} className="rounded-lg border border-amber-700/30 bg-amber-500/10 px-3 py-2.5 text-xs text-amber-400">
              {warning}
            </div>
          ))}
        </div>
      ) : null}

      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <MiniMetric label="当前价格" value={fmtNumber(state?.snapshot?.lastPrice)} />
        <MiniMetric label="当日振幅" value={fmtPct(intraday?.rangePct)} />
        <MiniMetric label="振幅点数" value={fmtPts(intraday?.rangePoints)} />
        <MiniMetric label="历史分位" value={fmtPct(intraday?.rankPct)} />
        <MiniMetric label="区间位置" value={fmtPct(intraday?.positionPct)} />
        <MiniMetric label="75% / 90% 剩余" value={`${fmtPts(intraday?.p75LeftPoints)} / ${fmtPts(intraday?.p90LeftPoints)}`} />
      </div>

      <div className="mt-3 rounded-[18px] border border-toptrader-line bg-gradient-to-r from-toptrader-soft via-toptrader-panel to-toptrader-brand/5 px-4 py-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-[12px] font-bold text-toptrader-accent">当前判断</div>
            <div className="mt-1.5 text-xl font-black tracking-tight text-toptrader-accent">
              {status?.label || '--'}
            </div>
          </div>
          <span className="rounded-full bg-toptrader-panel px-2.5 py-1.5 text-[11px] font-bold text-toptrader-muted shadow-sm">
            200 日样本
          </span>
        </div>
        <p className="mt-2 text-xs leading-6 text-toptrader-muted">{status?.message || '等待实时数据。'}</p>
      </div>
    </section>
  )
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-toptrader-line bg-toptrader-panel px-3 py-3 shadow-sm">
      <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-toptrader-muted">{label}</div>
      <div className="mt-1.5 text-lg font-black tracking-tight text-toptrader-accent">{value}</div>
    </div>
  )
}
