import { useEffect, useMemo, useState } from 'react'
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { WorkspaceProvider, useWorkspace } from './contexts/WorkspaceContext'
import { useKeyboard } from './hooks/useKeyboard'
import { displayValue, formatTradeDate } from './utils/display'
import { DataConsoleView } from './views/DataConsoleView'
import { HistoryView } from './views/HistoryView'
import { IntradayView } from './views/IntradayView'
import { PostmarketView } from './views/PostmarketView'
import { PremarketView } from './views/PremarketView'
import { ReferenceView } from './views/ReferenceView'

const tabs = [
  { to: '/premarket', label: '盘前准备', shortLabel: '盘前', icon: '前' },
  { to: '/reference', label: '参考信息', shortLabel: '参考', icon: '参' },
  { to: '/intraday', label: '盘中执行', shortLabel: '盘中', icon: '中' },
  { to: '/postmarket', label: '盘后闭环', shortLabel: '盘后', icon: '后' },
  { to: '/history', label: '历史复查', shortLabel: '历史', icon: '史' },
]

export default function App() {
  return (
    <WorkspaceProvider>
      <AppShell />
    </WorkspaceProvider>
  )
}

function AppShell() {
  const { state, switchMarket, switchTheme } = useWorkspace()
  const location = useLocation()

  const currentRecord = state?.recentRecords.find((record) => record.isCurrent)
  const activeTab = tabs.find((tab) => location.pathname.startsWith(tab.to)) ?? tabs[0]
  const isPremarketPage = activeTab.to === '/premarket'
  const currentModeLabel = currentRecord
    ? displayValue(currentRecord.market === 'US' ? currentRecord.primaryInstrument : currentRecord.tradingMode)
    : ''
  const tradeCountLabel =
    currentRecord?.tradeCount === undefined ? '交易数 --' : `交易数 ${currentRecord.tradeCount}`
  const theme = state?.theme === 'light' ? 'light' : 'dark'
  const currentMarket = state?.currentMarket === 'US' ? 'US' : 'HK'

  const navigate = useNavigate()
  const keyboardHandlers = useMemo(
    () => ({
      '1': () => navigate('/premarket'),
      '2': () => navigate('/reference'),
      '3': () => navigate('/intraday'),
      '4': () => navigate('/postmarket'),
      '5': () => navigate('/history'),
      '0': () => navigate('/console'),
    }),
    [navigate],
  )
  useKeyboard(keyboardHandlers)

  return (
    <div className="min-h-screen bg-toptrader-mist text-toptrader-ink">
      <div className="tt-noise" />
      <div className="relative z-[1] flex min-h-screen flex-col lg:flex-row">
        <aside className="flex flex-col border-b border-toptrader-line bg-toptrader-panel/95 backdrop-blur-xl lg:sticky lg:top-0 lg:h-screen lg:w-[196px] lg:border-b-0 lg:border-r">
          <div className="flex items-center gap-2.5 px-4 py-4">
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-gradient-to-br from-teal-500 via-cyan-500 to-blue-500 text-sm font-black text-white shadow-[0_10px_22px_rgba(20,184,166,0.22)]">
              TT
            </div>
            <div>
              <div className="font-display text-base font-bold text-toptrader-ink">TrendGo</div>
            </div>
          </div>

          <nav className="hidden gap-1.5 overflow-x-auto px-3 pb-3 lg:grid lg:overflow-visible lg:pb-0" aria-label="Primary">
            {tabs.map((tab) => (
              <NavLink
                key={tab.to}
                to={tab.to}
                className={({ isActive }) =>
                  [
                    'group flex min-w-fit items-center gap-2.5 rounded-r-lg border-l-2 px-3 py-2.5 text-[13px] font-semibold transition',
                    isActive
                      ? 'border-toptrader-brand bg-toptrader-brand/6 text-toptrader-brand'
                      : 'border-transparent text-toptrader-muted hover:bg-toptrader-soft hover:text-toptrader-ink',
                  ].join(' ')
                }
              >
                <span className="grid h-7 w-7 place-items-center rounded-md border border-current/10 bg-toptrader-soft text-[11px] text-toptrader-ink shadow-sm">
                  {tab.icon}
                </span>
                <span className="min-w-0">
                  <span className="block lg:hidden">{tab.shortLabel}</span>
                  <span className="hidden lg:block">{tab.label}</span>
                </span>
              </NavLink>
            ))}
          </nav>

          <div className="mt-auto px-4 pb-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-toptrader-muted">Session</div>
            <div className="mt-1 text-[13px] font-bold text-toptrader-ink">
              <SessionTimer />
            </div>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-20 border-b border-toptrader-line/60 bg-toptrader-panel/88 px-4 py-2.5 backdrop-blur-xl lg:px-6">
            {isPremarketPage ? (
              <div className="flex justify-end">
                <div className="flex items-center gap-2">
                  <MarketToggle currentMarket={currentMarket} onToggle={(market) => void switchMarket(market)} />
                  <ThemeToggle onToggle={() => void switchTheme(theme === 'dark' ? 'light' : 'dark')} theme={theme} />
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-2.5">
                <h1 className="tt-heading-page text-lg lg:text-[1.45rem]">
                  {activeTab.label}
                </h1>

                <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                  <MarketToggle currentMarket={currentMarket} onToggle={(market) => void switchMarket(market)} />
                  <ThemeToggle onToggle={() => void switchTheme(theme === 'dark' ? 'light' : 'dark')} theme={theme} />
                  <HudPill value={formatTradeDate(state?.currentTradeDate)} />
                  <HudPill value={currentMarket === 'HK' ? '港股工作台' : '美股工作台'} />
                  <HudPill value={currentModeLabel || '未载入'} />
                  <HudPill value={tradeCountLabel} />
                  <span className="inline-flex items-center gap-1.5 rounded-md border border-toptrader-brand/20 bg-toptrader-brand/6 px-2.5 py-1.5 text-xs font-bold text-toptrader-brand">
                    <span className="inline-block h-2 w-2 rounded-full bg-toptrader-brand" />
                    已同步
                  </span>
                </div>
              </div>
            )}
          </header>

          <main className="mx-auto w-full max-w-[1480px] px-4 py-5 lg:px-6">
            <Routes>
              <Route path="/" element={<Navigate to="/premarket" replace />} />
              <Route path="/premarket" element={<PremarketView />} />
              <Route path="/reference" element={<ReferenceView />} />
              <Route path="/intraday" element={<IntradayView />} />
              <Route path="/postmarket" element={<PostmarketView />} />
              <Route path="/closeout" element={<Navigate to="/postmarket" replace />} />
              <Route path="/history" element={<HistoryView />} />
              <Route path="/today" element={<Navigate to="/premarket" replace />} />
              <Route path="/workbench" element={<Navigate to="/premarket" replace />} />
              <Route path="/review" element={<Navigate to="/postmarket" replace />} />
              <Route path="/console" element={<DataConsoleView />} />
              <Route path="/review-hub" element={<Navigate to="/history" replace />} />
            </Routes>
          </main>

          <nav className="fixed bottom-0 left-0 right-0 z-30 flex items-center justify-around border-t border-toptrader-line bg-toptrader-panel/95 px-2 py-2.5 backdrop-blur-xl lg:hidden" aria-label="Mobile navigation">
            {tabs.map((tab) => (
              <NavLink
                key={tab.to}
                to={tab.to}
                className={({ isActive }) =>
                  [
                    'flex flex-col items-center gap-1 rounded-lg px-3 py-1.5 text-[11px] font-semibold transition',
                    isActive
                      ? 'text-toptrader-brand'
                      : 'text-toptrader-muted',
                  ].join(' ')
                }
              >
                <span className="grid h-6 w-6 place-items-center rounded-md bg-toptrader-soft text-[10px]">
                  {tab.icon}
                </span>
                <span>{tab.shortLabel}</span>
              </NavLink>
            ))}
          </nav>
        </div>
      </div>
    </div>
  )
}

function MarketToggle({
  currentMarket,
  onToggle,
}: {
  currentMarket: 'HK' | 'US'
  onToggle: (market: 'HK' | 'US') => void
}) {
  return (
    <div className="inline-flex rounded-md border border-toptrader-line bg-toptrader-panel p-1 shadow-sm">
      <button
        className={[
          'rounded px-2.5 py-1.5 text-[12px] font-bold transition',
          currentMarket === 'HK' ? 'bg-toptrader-brand text-toptrader-mist' : 'text-toptrader-muted hover:text-toptrader-ink',
        ].join(' ')}
        onClick={() => onToggle('HK')}
        type="button"
      >
        港股
      </button>
      <button
        className={[
          'rounded px-2.5 py-1.5 text-[12px] font-bold transition',
          currentMarket === 'US' ? 'bg-toptrader-brand text-toptrader-mist' : 'text-toptrader-muted hover:text-toptrader-ink',
        ].join(' ')}
        onClick={() => onToggle('US')}
        type="button"
      >
        美股
      </button>
    </div>
  )
}

function ThemeToggle({
  onToggle,
  theme,
}: {
  onToggle: () => void
  theme: 'dark' | 'light'
}) {
  return (
    <button
      className="rounded-md border border-toptrader-line bg-toptrader-panel px-2.5 py-1.5 text-[12px] font-bold text-toptrader-ink shadow-sm transition hover:border-toptrader-brand/30 hover:text-toptrader-brand"
      onClick={onToggle}
      type="button"
    >
      {theme === 'dark' ? '切到白天' : '切到黑夜'}
    </button>
  )
}

function HudPill({ className = '', value }: { className?: string; value: string }) {
  return (
    <span className={['rounded-md border border-toptrader-line bg-toptrader-panel px-2.5 py-1.5 text-[12px] font-bold text-toptrader-ink shadow-sm', className].join(' ')}>
      {value}
    </span>
  )
}

function SessionTimer() {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const start = Date.now()
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000)
    return () => clearInterval(id)
  }, [])

  const h = Math.floor(elapsed / 3600)
  const m = Math.floor((elapsed % 3600) / 60)
  const s = elapsed % 60
  return <span className="font-mono tabular-nums">{String(h).padStart(2, '0')}:{String(m).padStart(2, '0')}:{String(s).padStart(2, '0')}</span>
}
