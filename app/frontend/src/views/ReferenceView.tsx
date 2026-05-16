import { HSIRangePanel } from '../components/HSIRangePanel'
import { Badge } from '../components/ui/Badge'
import { MetaRow } from '../components/ui/MetaRow'
import { useWorkspaceData } from '../hooks/useWorkspaceData'
import { displayValue, formatTradeDate } from '../utils/display'

function splitLines(raw: string) {
  return raw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

export function ReferenceView() {
  const { day } = useWorkspaceData()
  const isHsiMode = day?.base.market === 'HK' || day?.workbench.tradingMode === 'hsi_bull_bear_certificate'
  const hkWatchlist = splitLines(day?.workbench.hkWatchlist || '')
  const usWatchlist = splitLines(day?.workbench.usWatchlist || '')
  const focusTickers = day?.playbook.focusTickers || '--'

  return (
    <div className="space-y-3.5">
      <section className="tt-bento-panel">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="tt-heading-card">参考信息</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge label={formatTradeDate(day?.base.tradeDate)} tone="success" />
            <Badge label={displayValue(day?.base.market)} />
            <Badge label={displayValue(day?.workbench.tradingMode)} />
          </div>
        </div>

        <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
          <section className="rounded-lg border border-toptrader-line bg-toptrader-soft/35 px-3 py-3">
            <div className="text-[11px] font-semibold tracking-[0.08em] text-toptrader-muted">当前参考范围</div>
            <div className="mt-3 grid gap-2.5">
              <MetaRow label="当前市场" value={displayValue(day?.base.market)} />
              <MetaRow label="当前模式" value={displayValue(day?.workbench.tradingMode)} />
              <MetaRow label="主方向预判" value={displayValue(day?.workbench.mainDirection)} />
              <MetaRow label="当前状态" value={displayValue(day?.workbench.currentState)} />
              <MetaRow label="主看股票池" value={focusTickers} />
            </div>
          </section>

          <section className="rounded-lg border border-toptrader-line bg-toptrader-panel px-3 py-3">
            <div className="text-[11px] font-semibold tracking-[0.08em] text-toptrader-muted">资讯接入预留</div>
            <div className="mt-3 grid gap-2.5">
              <PlaceholderFeed title="实时资讯流" />
              <PlaceholderFeed title="事件与题材" />
              <PlaceholderFeed title="标的提醒" />
            </div>
          </section>
        </div>
      </section>

      <div className="tt-bento-grid">
        <div className="tt-bento-panel accent col-span-12 xl:col-span-8">
          {isHsiMode ? (
            <HSIRangePanel />
          ) : (
            <section className="tt-card p-4">
              <div className="text-xs font-black uppercase tracking-[0.18em] text-toptrader-sky">市场参考</div>
              <h2 className="mt-2 tt-heading-page">当前模式未启用恒指参考</h2>
              <p className="mt-2 text-xs leading-5 text-toptrader-muted">
                当前交易模式不是恒指牛熊证，先保留资讯与观察池信息；后续可在这里继续扩展美股参考模块。
              </p>
            </section>
          )}
        </div>

        <div className="tt-bento-panel col-span-12 xl:col-span-4">
          <div className="text-[11px] font-semibold tracking-[0.08em] text-toptrader-muted">观察标的</div>
          <div className="mt-3 space-y-3">
            <WatchlistCard
              emptyText="当前没有港股观察列表。"
              items={hkWatchlist}
              title="港股观察列表"
            />
            <WatchlistCard
              emptyText="当前没有美股观察列表。"
              items={usWatchlist}
              title="美股观察列表"
            />
          </div>
        </div>
      </div>
    </div>
  )
}

function PlaceholderFeed({ title }: { title: string }) {
  return (
    <div className="rounded-lg border border-dashed border-toptrader-line bg-toptrader-soft/30 px-3 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-[12px] font-semibold text-toptrader-accent">{title}</div>
        <span className="rounded-full bg-toptrader-soft px-2 py-0.5 text-[10px] font-semibold text-toptrader-muted">
          待接入
        </span>
      </div>
    </div>
  )
}

function WatchlistCard({
  emptyText,
  items,
  title,
}: {
  emptyText: string
  items: string[]
  title: string
}) {
  return (
    <section className="rounded-lg border border-toptrader-line bg-toptrader-panel px-3 py-3">
      <div className="text-[12px] font-semibold text-toptrader-accent">{title}</div>
      {items.length ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {items.map((item) => (
            <span
              key={item}
              className="rounded-md border border-toptrader-line bg-toptrader-soft/45 px-2.5 py-1.5 text-[11px] font-medium text-toptrader-ink"
            >
              {item}
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-xs leading-5 text-toptrader-muted">{emptyText}</p>
      )}
    </section>
  )
}
