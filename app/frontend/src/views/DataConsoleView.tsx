import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'

import { MarkdownPreview } from '../components/MarkdownPreview'
import { MetricCard } from '../components/MetricCard'
import { ReadonlyDayDetail } from '../components/review/ReadonlyDayDetail'
import { Toast, type ToastState } from '../components/Toast'
import { Badge } from '../components/ui/Badge'
import { MetaRow } from '../components/ui/MetaRow'
import { SummaryCard } from '../components/ui/SummaryCard'
import type {
  ArtifactPreview,
  ArtifactsOverview,
  DailyRecord,
  DayActionResponse,
  DayDiagnostics,
  HistoryOverview,
  StateActionResponse,
  WorkspaceOverview,
} from '../types'
import { apiClient } from '../utils/apiClient'
import { displayValue, formatTradeDate } from '../utils/display'
import { formatHkdSummaryAmount, formatNumber, formatTradePnl, sumTradesPnlHkd, winRateText } from '../utils/money'
import { emitWorkspaceRefresh } from '../utils/workspaceEvents'

type ConsoleState = {
  artifacts: ArtifactsOverview | null
  history: HistoryOverview | null
  loading: boolean
  error: string
  selectedHistoryPath: string
  selectedHistoryDay: DailyRecord | null
  selectedHistoryLoading: boolean
  selectedHistoryError: string
  workspace: WorkspaceOverview | null
}

const initialState: ConsoleState = {
  artifacts: null,
  history: null,
  loading: true,
  error: '',
  selectedHistoryPath: '',
  selectedHistoryDay: null,
  selectedHistoryLoading: false,
  selectedHistoryError: '',
  workspace: null,
}

export function DataConsoleView() {
  const [state, setState] = useState<ConsoleState>(initialState)
  const [toast, setToast] = useState<ToastState | null>(null)

  const loadConsole = async (options?: { historyWindow?: string; sampleFilter?: string }) => {
    setState((current) => ({ ...current, loading: true, error: '' }))
    try {
      const [workspace, artifacts, history] = await Promise.all([
        apiClient.get<WorkspaceOverview>('/api/workspace/overview'),
        apiClient.get<ArtifactsOverview>('/api/artifacts/overview'),
        apiClient.get<HistoryOverview>(
          `/api/history/overview${buildHistoryQuery(options?.historyWindow, options?.sampleFilter)}`,
        ),
      ])
      setState((current) => ({
        ...current,
        workspace,
        artifacts,
        history,
        loading: false,
        error: '',
      }))
    } catch (error) {
      setState((current) => ({
        ...current,
        loading: false,
        error: error instanceof Error ? error.message : '加载全量数据台失败。',
      }))
    }
  }

  useEffect(() => {
    void loadConsole()
  }, [])

  const loadHistoryDay = async (path: string) => {
    setState((current) => ({
      ...current,
      selectedHistoryPath: path,
      selectedHistoryLoading: true,
      selectedHistoryError: '',
    }))
    try {
      const day = await apiClient.get<DailyRecord>(`/api/records?path=${encodeURIComponent(path)}`)
      setState((current) => ({
        ...current,
        selectedHistoryDay: day,
        selectedHistoryLoading: false,
      }))
    } catch (error) {
      setState((current) => ({
        ...current,
        selectedHistoryDay: null,
        selectedHistoryLoading: false,
        selectedHistoryError: error instanceof Error ? error.message : '加载历史详情失败。',
      }))
    }
  }

  const refreshAll = async () => {
    await loadConsole({
      historyWindow: state.history?.window,
      sampleFilter: state.history?.sampleFilter,
    })
    emitWorkspaceRefresh()
    setToast({ message: '全量数据台已刷新。', tone: 'success' })
  }

  const switchCurrentRecord = async (tradeDate: string, market: string) => {
    try {
      const response = await apiClient.put<StateActionResponse>('/api/state/current-record', { tradeDate, market })
      emitWorkspaceRefresh()
      await loadConsole({
        historyWindow: state.history?.window,
        sampleFilter: state.history?.sampleFilter,
      })
      setToast({ message: response.message, tone: 'success' })
    } catch (error) {
      setToast({ message: error instanceof Error ? error.message : '切换当前交易日失败。', tone: 'error' })
    }
  }

  const updateHistoryWindow = async (nextWindow: string) => {
    try {
      await apiClient.put<StateActionResponse>('/api/state/review-hub', {
        sampleFilter: state.history?.sampleFilter ?? 'all',
        window: nextWindow,
      })
      await loadConsole({
        historyWindow: nextWindow,
        sampleFilter: state.history?.sampleFilter,
      })
      setToast({ message: `历史窗口已切换为 ${nextWindow === 'all' ? '全部' : `近 ${nextWindow} 日`}。`, tone: 'success' })
    } catch (error) {
      setToast({ message: error instanceof Error ? error.message : '切换历史窗口失败。', tone: 'error' })
    }
  }

  const generateArtifact = async (kind: 'closeout' | 'summary' | 'audit') => {
    try {
      if (kind === 'closeout' && day) {
        await apiClient.post<ArtifactPreview | { exists: boolean }>('/api/day-records/closeout', {
          market: day.base.market,
          regenerate: true,
          tradeDate: day.base.tradeDate,
        })
      } else if (kind === 'summary') {
        await apiClient.post<ArtifactPreview>('/api/artifacts/trial-summary', { regenerate: true })
      } else if (kind === 'audit') {
        await apiClient.post<ArtifactPreview>('/api/artifacts/field-audit', { regenerate: true })
      }
      await loadConsole({
        historyWindow: state.history?.window,
        sampleFilter: state.history?.sampleFilter,
      })
      emitWorkspaceRefresh()
      setToast({
        message:
          kind === 'closeout'
            ? '归档草稿已生成并刷新。'
            : kind === 'summary'
              ? '试验总结已生成并刷新。'
              : '字段审计已生成并刷新。',
        tone: 'success',
      })
    } catch (error) {
      setToast({ message: error instanceof Error ? error.message : '生成产物失败。', tone: 'error' })
    }
  }

  const syncReviewAcceptance = async (day: DailyRecord) => {
    try {
      const response = await apiClient.post<DayActionResponse>(
        `/api/days/${day.base.dayNumber}/review/acceptance`,
        {
          tradeCount: day.review.tradeCount,
          pnl: day.review.pnl,
          bestTradeNote: day.review.bestTradeNote,
          worstTradeNote: day.review.worstTradeNote,
          executionIssue: day.review.executionIssue,
          emotionIssue: day.review.emotionIssue,
          riskIssue: day.review.riskIssue,
          nextDayOneFix: day.review.nextDayOneFix,
          winRate: day.review.winRate,
          maxLossTrade: day.review.maxLossTrade,
          marketIssue: day.review.marketIssue,
          setupIssue: day.review.setupIssue,
          preMarketDone: day.validation.preMarketDone,
          intradayRecordComplete: day.validation.intradayRecordComplete,
          postMarketReviewDone: day.validation.postMarketReviewDone,
          impulsiveTradeDetected: day.validation.impulsiveTradeDetected,
          noStopLossTradeDetected: day.validation.noStopLossTradeDetected,
          emotionalOvertradeDetected: day.validation.emotionalOvertradeDetected,
          noTradeDay: day.validation.noTradeDay,
          noTradeNote: day.validation.noTradeNote,
          mainIssueOfDay: day.validation.mainIssueOfDay,
          mainImprovementOfDay: day.validation.mainImprovementOfDay,
        },
      )
      emitWorkspaceRefresh()
      await loadConsole({
        historyWindow: state.history?.window,
        sampleFilter: state.history?.sampleFilter,
      })
      setToast({ message: response.message, tone: 'success' })
    } catch (error) {
      setToast({ message: error instanceof Error ? error.message : '终局验收复盘失败。', tone: 'error' })
    }
  }

  if (state.loading) {
    return <section className="tt-card p-5 text-sm text-toptrader-muted">正在加载全量数据台…</section>
  }

  if (state.error || !state.workspace || !state.artifacts || !state.history) {
    return <section className="tt-card p-5 text-sm text-toptrader-rose">{state.error || '全量数据台暂不可用。'}</section>
  }

  const { workspace, artifacts, history } = state
  const day = workspace.currentDay
  const diagnostics = workspace.diagnostics

  return (
    <section className="space-y-4">
      <Toast onClear={() => setToast(null)} toast={toast} />
      <article className="tt-card tt-hero p-5">
        <div className="relative z-10 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-body text-[22px] font-semibold tracking-tight text-toptrader-ink">全量数据台</h2>
            <p className="mt-1.5 max-w-3xl text-[13px] leading-5 text-toptrader-muted">
              这里优先把后端当前已经有的状态、单日数据、诊断信号、统计结果和归档产物全部放出来，后续再基于真实信息密度做归类和减法。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge label={workspace.state.currentTradeDate ? formatTradeDate(workspace.state.currentTradeDate) : '未载入交易日'} tone="success" />
            <Badge label={workspace.state.currentMarket === 'US' ? '当前：美股工作台' : '当前：港股工作台'} />
            <Badge label={`最近记录 ${workspace.state.recentRecords.length}`} />
            <Badge label={`归档 ${workspace.state.recentCloseouts.length}`} />
          </div>
        </div>
        <div className="relative z-10 mt-3 flex flex-wrap gap-2.5">
          <button className="tt-secondary px-3 py-2 text-xs font-bold" onClick={() => void refreshAll()} type="button">
            刷新数据台
          </button>
          {day?.isCurrent ? (
            <>
              <button className="tt-secondary px-3 py-2 text-xs font-bold" onClick={() => void generateArtifact('closeout')} type="button">
                重生成归档
              </button>
              <button className="tt-secondary px-3 py-2 text-xs font-bold" onClick={() => void syncReviewAcceptance(day)} type="button">
                终局验收复盘
              </button>
            </>
          ) : null}
          <button className="tt-secondary px-3 py-2 text-xs font-bold" onClick={() => void generateArtifact('summary')} type="button">
            生成试验总结
          </button>
          <button className="tt-secondary px-3 py-2 text-xs font-bold" onClick={() => void generateArtifact('audit')} type="button">
            生成字段审计
          </button>
        </div>
      </article>

      <section className="tt-bento-grid">
        <div className="col-span-12 xl:col-span-8 space-y-5">
          <WorkspaceOverviewSection onSwitchCurrentRecord={switchCurrentRecord} workspace={workspace} />
          {day ? <CurrentDayFullSection day={day} diagnostics={diagnostics} onGenerateCloseout={() => void generateArtifact('closeout')} /> : <EmptyCurrentDaySection />}
          <ArtifactsSection
            artifacts={artifacts}
            currentDayNumber={day?.base.dayNumber}
            onGenerateAudit={() => void generateArtifact('audit')}
            onGenerateCloseout={() => day ? void generateArtifact('closeout') : undefined}
            onGenerateSummary={() => void generateArtifact('summary')}
          />
        </div>
        <div className="col-span-12 xl:col-span-4 space-y-5">
          <HistoryStatsSection history={history} onWindowChange={updateHistoryWindow} />
          <RecentListsSection workspace={workspace} />
        </div>
      </section>

      <HistoryDetailsSection
        history={history}
        selectedHistoryDay={state.selectedHistoryDay}
        selectedHistoryError={state.selectedHistoryError}
        selectedHistoryLoading={state.selectedHistoryLoading}
        selectedHistoryPath={state.selectedHistoryPath}
        onSelect={loadHistoryDay}
      />
    </section>
  )
}

function WorkspaceOverviewSection({
  workspace,
  onSwitchCurrentRecord,
}: {
  workspace: WorkspaceOverview
  onSwitchCurrentRecord: (tradeDate: string, market: string) => void
}) {
  const currentRecord = workspace.state.recentRecords.find((item) => item.isCurrent)
  return (
    <section className="tt-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-2.5">
        <div>
          <h3 className="font-body text-lg font-semibold text-toptrader-ink">工作区状态</h3>
          <p className="mt-1 text-[13px] text-toptrader-muted">当前状态、最近记录与最近产物指针全部集中展示。</p>
        </div>
        {currentRecord ? <Badge label={`当前模式 ${displayValue(currentRecord.market === 'US' ? 'us_stock_options' : currentRecord.tradingMode)}`} tone="success" /> : null}
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard accent label="当前交易日" value={workspace.state.currentTradeDate ? formatTradeDate(workspace.state.currentTradeDate) : '--'} />
        <MetricCard label="当前市场" value={workspace.state.currentMarket === 'US' ? '美股工作台' : '港股工作台'} />
        <MetricCard label="近期开仓记录" value={workspace.state.recentRecords.length} />
        <MetricCard label="美元/港币" value={formatNumber(workspace.state.usdHkdRate)} />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <MetaRow label="当前记录路径" value={workspace.state.currentRecordPath || '--'} />
        <MetaRow label="当前归档路径" value={workspace.state.currentCloseoutPath || '--'} />
        <MetaRow label="当前总结路径" value={workspace.state.currentSummaryPath || '--'} />
        <MetaRow label="当前审计路径" value={workspace.state.currentAuditPath || '--'} />
      </div>
      <div className="mt-4">
        <h4 className="font-body text-sm font-semibold text-toptrader-ink">切换当前交易日</h4>
        <div className="mt-2 flex flex-wrap gap-2">
          {workspace.state.recentRecords.map((item) => (
            <button
              key={`${item.tradeDate}-${item.market}`}
              className={[
                'rounded-lg px-2.5 py-1.5 text-[11px] font-bold transition',
                item.isCurrent
                  ? 'bg-toptrader-brand/15 text-toptrader-brand'
                  : 'border border-toptrader-line bg-toptrader-panel text-toptrader-muted hover:text-toptrader-ink',
              ].join(' ')}
              disabled={item.isCurrent}
              onClick={() => onSwitchCurrentRecord(item.tradeDate, item.market)}
              type="button"
            >
              {formatTradeDate(item.tradeDate)} · {item.market === 'US' ? '美股' : '港股'}
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}

function CurrentDayFullSection({
  day,
  diagnostics,
  onGenerateCloseout,
}: {
  day: DailyRecord
  diagnostics: DayDiagnostics | null
  onGenerateCloseout: () => void
}) {
  const pnlHkd = sumTradesPnlHkd(day.trades)
  return (
    <section className="space-y-4">
      <section className="tt-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-2.5">
          <div>
            <h3 className="font-body text-lg font-semibold text-toptrader-ink">当前交易日完整记录</h3>
            <p className="mt-1 text-[13px] text-toptrader-muted">把单日记录的所有主要区块先完整展开，包括之前没被前端充分展示的字段。</p>
          </div>
          <Badge label={day.isCurrent ? '当前可编辑' : '历史只读'} tone={day.isCurrent ? 'success' : 'neutral'} />
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <SummaryCard label="日期" value={formatTradeDate(day.base.tradeDate)} />
          <SummaryCard label="市场 / 模式" value={`${displayValue(day.base.market)} / ${displayValue(day.base.market === 'US' ? 'us_stock_options' : day.workbench.tradingMode)}`} />
          <SummaryCard label="交易数 / 胜率" value={`${day.trades.length} / ${winRateText(day.trades)}`} />
          <SummaryCard label="总盈亏(HKD)" value={formatHkdSummaryAmount(pnlHkd)} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2.5">
          <Badge label={day.closeout.exists ? '已有归档草稿' : '还没有归档草稿'} tone={day.closeout.exists ? 'success' : 'neutral'} />
          <Badge label={day.closeout.stale ? '归档待刷新' : '归档已同步'} tone={day.closeout.stale ? 'warning' : 'success'} />
          {day.isCurrent ? (
            <button className="tt-secondary px-3 py-2 text-xs font-bold" onClick={onGenerateCloseout} type="button">
              立即生成归档
            </button>
          ) : null}
        </div>
      </section>

      {diagnostics ? <DiagnosticsSection diagnostics={diagnostics} /> : null}

      <section className="tt-bento-grid">
        <SectionCard className="col-span-12 lg:col-span-6" title="基础信息">
          <MetaGrid
            items={[
              ['交易日期', formatTradeDate(day.base.tradeDate)],
              ['市场', displayValue(day.base.market)],
              ['主交易工具', displayValue(day.base.primaryInstrument)],
              ['操作者', day.base.operator || '--'],
              ['记录归属', day.base.recordOwner || '--'],
              ['记录路径', day.sourceRecordPath || '--'],
            ]}
          />
        </SectionCard>
        <SectionCard className="col-span-12 lg:col-span-6" title="盘前状态">
          <MetaGrid
            items={[
              ['今日是否交易', boolText(day.preMarket.tradingToday)],
              ['状态', displayValue(day.preMarket.state)],
              ['是否遵守常规规则', boolText(day.preMarket.followNormalRules)],
              ['关键提醒', day.preMarket.keyReminder || '--'],
              ['备注', day.preMarket.note || '--'],
            ]}
          />
        </SectionCard>
        <SectionCard className="col-span-12" title="作战台">
          <MetaGrid
            items={[
              ['交易模式', displayValue(day.workbench.tradingMode)],
              ['主方向', displayValue(day.workbench.mainDirection)],
              ['当前状态', displayValue(day.workbench.currentState)],
              ['上方压力', day.workbench.upperPressure || '--'],
              ['下方支撑', day.workbench.lowerSupport || '--'],
              ['枢轴位', day.workbench.pivotLevel || '--'],
              ['使用本金', stringify(day.workbench.capitalUsed)],
              ['盈利目标%', stringify(day.workbench.profitTargetPct)],
              ['港股观察列表', day.workbench.hkWatchlist || '--'],
              ['美股观察列表', day.workbench.usWatchlist || '--'],
              ['盘后总结', day.workbench.postMarketSummary || '--'],
            ]}
          />
        </SectionCard>
        <SectionCard className="col-span-12" title="专项计划">
          <MetaGrid
            items={[
              ['开盘计划', displayValue(day.playbook.openingPlan)],
              ['主练形态', displayValue(day.playbook.focusSetup)],
              ['开盘 30 分钟关键信号', day.playbook.open30KeySignal || '--'],
              ['牛熊证过滤备注', day.playbook.certificateFilterNote || '--'],
              ['异常场景计划', day.playbook.abnormalPlan || '--'],
              ['期权时段计划', displayValue(day.playbook.optionSessionPlan)],
              ['关注标的', day.playbook.focusTickers || '--'],
              ['期权主练形态', displayValue(day.playbook.optionFocusSetup)],
              ['期权入场信号', day.playbook.optionEntrySignal || '--'],
              ['期权合约过滤', day.playbook.optionContractFilter || '--'],
              ['期权风控计划', day.playbook.optionRiskPlan || '--'],
              ['期权事件风险计划', day.playbook.optionEventRiskPlan || '--'],
            ]}
          />
        </SectionCard>
        <SectionCard className="col-span-12 xl:col-span-6" title="盘后复盘">
          <MetaGrid
            items={[
              ['复盘日期', formatTradeDate(day.review.reviewDate)],
              ['盈亏', day.review.pnl || '--'],
              ['交易数', String(day.review.tradeCount ?? '--')],
              ['胜率', day.review.winRate || '--'],
              ['最大亏损交易', day.review.maxLossTrade || '--'],
              ['最好动作', day.review.bestTradeNote || '--'],
              ['最差问题', day.review.worstTradeNote || '--'],
              ['市场问题', day.review.marketIssue || '--'],
              ['执行问题', day.review.executionIssue || '--'],
              ['情绪问题', day.review.emotionIssue || '--'],
              ['风控问题', day.review.riskIssue || '--'],
              ['形态问题', day.review.setupIssue || '--'],
              ['明天只改一件事', day.review.nextDayOneFix || '--'],
            ]}
          />
        </SectionCard>
        <SectionCard className="col-span-12 xl:col-span-6" title="验证与归档">
          <MetaGrid
            items={[
              ['盘前完成', boolText(day.validation.preMarketDone)],
              ['盘中记录完成', boolText(day.validation.intradayRecordComplete)],
              ['盘后复盘完成', boolText(day.validation.postMarketReviewDone)],
              ['出现冲动交易', boolText(day.validation.impulsiveTradeDetected)],
              ['出现无止损/止损失守', boolText(day.validation.noStopLossTradeDetected)],
              ['出现情绪化过度交易', boolText(day.validation.emotionalOvertradeDetected)],
              ['空仓日', boolText(day.validation.noTradeDay)],
              ['空仓说明', day.validation.noTradeNote || '--'],
              ['当日主要问题', day.validation.mainIssueOfDay || '--'],
              ['当日主要改进', day.validation.mainImprovementOfDay || '--'],
            ]}
          />
        </SectionCard>
      </section>

      <FullTradesSection day={day} />
      <FullEventsSection day={day} />
    </section>
  )
}

function DiagnosticsSection({ diagnostics }: { diagnostics: DayDiagnostics }) {
  return (
    <section className="tt-card p-5">
      <div>
        <h3 className="font-body text-lg font-semibold text-toptrader-ink">诊断信号</h3>
        <p className="mt-1 text-[13px] text-toptrader-muted">后端已算好的待办、流程、健康度、决策门和风险状态统一前端化，不在前端重复计算规则。</p>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard label="当日盈亏" value={diagnostics.daySummary.pnlTotal} />
        <SummaryCard label="盈亏%" value={diagnostics.daySummary.pnlPct} />
        <SummaryCard label="目标距离" value={diagnostics.daySummary.targetDistance} />
        <SummaryCard label="A/B/C" value={diagnostics.daySummary.gradeCounts} />
      </div>
      <div className="mt-4 grid gap-3 xl:grid-cols-3">
        <DiagnosticStatusCard
          action={diagnostics.decisionGate.action}
          details={[...diagnostics.decisionGate.blockers, ...diagnostics.decisionGate.cautions, ...diagnostics.decisionGate.strengths]}
          label={diagnostics.decisionGate.label}
          title="决策门"
          tone={statusTone(diagnostics.decisionGate.status)}
        />
        <DiagnosticStatusCard
          action={diagnostics.riskState.action}
          details={[...diagnostics.riskState.blockers, ...diagnostics.riskState.cautions, ...diagnostics.riskState.strengths]}
          label={diagnostics.riskState.label}
          title="风险控制器"
          tone={statusTone(diagnostics.riskState.status)}
        />
        <DiagnosticStatusCard
          action={diagnostics.executionLock.action}
          details={diagnostics.executionLock.reasons}
          label={diagnostics.executionLock.label}
          title="执行锁"
          tone={statusTone(diagnostics.executionLock.status)}
        />
      </div>
      <div className="mt-4 grid gap-3 xl:grid-cols-3">
        <ListCard
          items={diagnostics.todoItems.map((item) => item.text)}
          title="待办事项"
        />
        <ListCard
          items={diagnostics.workflowSteps.map((item) => `${item.done ? '已完成' : '待补齐'} · ${item.label} · ${item.note}`)}
          title="流程步骤"
        />
        <ListCard
          items={diagnostics.recordHealthItems.map((item) => `${item.level.toUpperCase()} · ${item.text}`)}
          title="记录健康度"
        />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <SectionCard title="复盘默认值">
          <MetaGrid
            items={[
              ['盈亏', diagnostics.reviewDefaults.pnl || '--'],
              ['盈亏提示', diagnostics.reviewDefaults.pnlHint || '--'],
              ['交易数', diagnostics.reviewDefaults.tradeCount || '--'],
              ['交易数提示', diagnostics.reviewDefaults.tradeCountHint || '--'],
            ]}
          />
        </SectionCard>
        <SectionCard title="上一日上下文">
          <MetaGrid
            items={[
              ['交易日期', diagnostics.previousContext.tradeDate ? formatTradeDate(diagnostics.previousContext.tradeDate) : '--'],
              ['交易模式', displayValue(diagnostics.previousContext.tradingMode)],
              ['计划', displayValue(diagnostics.previousContext.plan)],
              ['形态', displayValue(diagnostics.previousContext.setup)],
              ['主要问题', diagnostics.previousContext.mainIssue || '--'],
              ['主要改进', diagnostics.previousContext.improvement || '--'],
              ['下一步修正', diagnostics.previousContext.nextFix || '--'],
            ]}
          />
        </SectionCard>
      </div>
    </section>
  )
}

function FullTradesSection({ day }: { day: DailyRecord }) {
  return (
    <section className="tt-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-2.5">
        <div>
          <h3 className="font-body text-lg font-semibold text-toptrader-ink">交易流水完整明细</h3>
          <p className="mt-1 text-[13px] text-toptrader-muted">不仅显示交易摘要，也展开之前没充分展示的四条件、异常场景、情绪、备注和港币折算信息。</p>
        </div>
        <Badge label={`${day.trades.length} 笔`} />
      </div>
      <div className="mt-3 space-y-3">
        {day.trades.length ? day.trades.map((trade) => {
          const pnl = formatTradePnl(trade)
          return (
            <div key={trade.tradeId} className="rounded-xl border border-toptrader-line bg-toptrader-panel px-4 py-4">
              <div className="flex flex-wrap items-start justify-between gap-2.5">
                <div>
                  <div className="text-base font-semibold text-toptrader-accent">{trade.tradeId}</div>
                  <div className="mt-1 text-[13px] text-toptrader-muted">
                    {trade.tradeTime || '--'} → {trade.exitTime || '--'} · {trade.instrumentCode || '--'} · {displayValue(trade.direction)} · {displayValue(trade.setupType)}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-base font-semibold text-toptrader-accent">{pnl.primary}</div>
                  <div className="mt-1 text-xs text-toptrader-muted">港币折算 {formatHkdSummaryAmount(trade.pnlAmountHkd)}</div>
                </div>
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <MetaRow label="ABC 等级" value={displayValue(trade.abcGrade)} />
                <MetaRow label="形态评分" value={stringify(trade.setupScore)} />
                <MetaRow label="形态已验证" value={nullableBoolText(trade.setupValidated)} />
                <MetaRow label="时段窗口" value={displayValue(trade.sessionWindow)} />
                <MetaRow label="牛熊证方向/期权方向" value={displayValue(trade.certificateSide)} />
                <MetaRow label="工具类型" value={displayValue(trade.instrumentType)} />
                <MetaRow label="底层标的" value={displayValue(trade.underlying)} />
                <MetaRow label="仓位大小" value={trade.positionSize || '--'} />
                <MetaRow label="入场价" value={stringify(trade.entryPrice)} />
                <MetaRow label="止损价" value={stringify(trade.stopLoss)} />
                <MetaRow label="目标价" value={stringify(trade.targetPrice)} />
                <MetaRow label="盈亏比" value={stringify(trade.riskRewardRatio)} />
                <MetaRow label="方向明确" value={nullableBoolText(trade.directionClear)} />
                <MetaRow label="位置合适" value={nullableBoolText(trade.locationOk)} />
                <MetaRow label="确认到位" value={nullableBoolText(trade.confirmationOk)} />
                <MetaRow label="风险清楚" value={nullableBoolText(trade.riskClear)} />
                <MetaRow label="过滤通过" value={nullableBoolText(trade.certificateFilterPassed)} />
                <MetaRow label="按计划执行" value={boolText(trade.followedPlan)} />
                <MetaRow label="规则违规" value={boolText(trade.ruleViolation)} />
                <MetaRow label="结果" value={displayValue(trade.result)} />
                <MetaRow label="异常场景" value={displayValue(trade.abnormalScenario)} />
                <MetaRow label="情绪状态" value={displayValue(trade.emotionState)} />
                <MetaRow label="开仓前情绪" value={displayValue(trade.preTradeEmotion)} />
                <MetaRow label="平仓后情绪" value={displayValue(trade.postTradeEmotion)} />
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <MetaRow label="入场原因" value={trade.entryReason || '--'} />
                <MetaRow label="出场原因" value={trade.exitReason || '--'} />
                <MetaRow label="违规说明" value={trade.violationNote || '--'} />
                <MetaRow label="复盘备注" value={trade.reviewNote || '--'} />
                <MetaRow label="截图备注" value={trade.screenshotNote || '--'} />
              </div>
            </div>
          )
        }) : (
          <div className="rounded-xl border border-dashed border-toptrader-line bg-toptrader-soft/30 px-4 py-6 text-sm text-toptrader-muted">当前没有交易记录。</div>
        )}
      </div>
    </section>
  )
}

function FullEventsSection({ day }: { day: DailyRecord }) {
  return (
    <section className="tt-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-2.5">
        <div>
          <h3 className="font-body text-lg font-semibold text-toptrader-ink">纪律事件完整明细</h3>
          <p className="mt-1 text-[13px] text-toptrader-muted">把事件类型、严重级别、采取动作、后续说明和关联交易全部展开。</p>
        </div>
        <Badge label={`${day.events.length} 条`} />
      </div>
      <div className="mt-3 space-y-3">
        {day.events.length ? day.events.map((event) => (
          <div key={event.eventId} className="rounded-xl border border-toptrader-line bg-toptrader-panel px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-2.5">
              <div>
                <div className="text-base font-semibold text-toptrader-accent">{event.eventId}</div>
                <div className="mt-1 text-[13px] text-toptrader-muted">{event.time || '--'} · {displayValue(event.eventType)} · {displayValue(event.severity)}</div>
              </div>
              <Badge label={event.linkedTradeId ? `关联 ${event.linkedTradeId}` : '未关联交易'} tone={event.linkedTradeId ? 'success' : 'neutral'} />
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <MetaRow label="触发原因" value={event.triggerReason || '--'} />
              <MetaRow label="采取动作" value={event.actionTaken || '--'} />
              <MetaRow label="后续说明" value={event.followUpNote || '--'} />
              <MetaRow label="关联交易" value={event.linkedTradeId || '--'} />
            </div>
          </div>
        )) : (
          <div className="rounded-xl border border-dashed border-toptrader-line bg-toptrader-soft/30 px-4 py-6 text-sm text-toptrader-muted">当前没有纪律事件。</div>
        )}
      </div>
    </section>
  )
}

function ArtifactsSection({
  artifacts,
  currentDayNumber,
  onGenerateAudit,
  onGenerateCloseout,
  onGenerateSummary,
}: {
  artifacts: ArtifactsOverview
  currentDayNumber?: number
  onGenerateAudit: () => void
  onGenerateCloseout: () => void
  onGenerateSummary: () => void
}) {
  return (
    <section className="tt-card p-5">
      <div>
        <h3 className="font-body text-lg font-semibold text-toptrader-ink">产物预览</h3>
        <p className="mt-1 text-[13px] text-toptrader-muted">归档草稿、试验总结、字段审计三类产物先全部前端化，包括路径、存在状态和正文预览。</p>
      </div>
      <div className="mt-3 flex flex-wrap gap-2.5">
        {currentDayNumber ? (
          <button className="tt-secondary px-3 py-2 text-xs font-bold" onClick={onGenerateCloseout} type="button">
            重生成当前归档
          </button>
        ) : null}
        <button className="tt-secondary px-3 py-2 text-xs font-bold" onClick={onGenerateSummary} type="button">
          生成试验总结
        </button>
        <button className="tt-secondary px-3 py-2 text-xs font-bold" onClick={onGenerateAudit} type="button">
          生成字段审计
        </button>
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <ArtifactCard artifact={artifacts.currentCloseout} title="当前归档草稿" />
        <ArtifactCard artifact={artifacts.currentSummary} title="当前试验总结" />
        <ArtifactCard artifact={artifacts.currentAudit} title="当前字段审计" />
      </div>
    </section>
  )
}

function HistoryStatsSection({
  history,
  onWindowChange,
}: {
  history: HistoryOverview
  onWindowChange: (window: string) => void
}) {
  const stats = history.stats
  return (
    <section className="tt-card p-5">
      <div>
        <h3 className="font-body text-lg font-semibold text-toptrader-ink">历史统计</h3>
        <p className="mt-1 text-[13px] text-toptrader-muted">把复盘中心统计接口里的字段尽量全部挂出来，后续再决定哪些留主视图、哪些折叠。</p>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {['5', '10', 'all'].map((option) => (
          <button
            key={option}
            className={[
              'rounded-lg px-2.5 py-1.5 text-[11px] font-bold transition',
              history.window === option
                ? 'bg-toptrader-brand/15 text-toptrader-brand'
                : 'border border-toptrader-line bg-toptrader-panel text-toptrader-muted hover:text-toptrader-ink',
            ].join(' ')}
            onClick={() => onWindowChange(option)}
            type="button"
          >
            {option === 'all' ? '全部' : `近 ${option} 日`}
          </button>
        ))}
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <SummaryCard label="范围" value={history.window === 'all' ? '全部' : `近 ${history.window} 日`} />
        <SummaryCard label="样本筛选" value={history.sampleFilter} />
        <SummaryCard label="交易天数" value={stats.dayCount} />
        <SummaryCard label="有交易日" value={stats.tradeDayCount} />
        <SummaryCard label="空仓日" value={stats.noTradeDayCount} />
        <SummaryCard label="总交易数" value={stats.tradeCount} />
        <SummaryCard label="总盈亏(HKD)" value={formatHkdSummaryAmount(stats.totalPnl)} />
        <SummaryCard label="平均日盈亏(HKD)" value={formatHkdSummaryAmount(stats.avgDailyPnl)} />
        <SummaryCard label="违规次数" value={stats.violationCount} />
        <SummaryCard label="按计划率" value={stats.planFollowRate === null ? '--' : `${stats.planFollowRate.toFixed(1)}%`} />
        <SummaryCard label="赢/亏/平" value={`${stats.winCount}/${stats.lossCount}/${stats.breakevenCount}`} />
        <SummaryCard label="归档同步日" value={stats.closeoutSyncedDays} />
        <SummaryCard label="冲动交易日" value={stats.impulsiveDays} />
        <SummaryCard label="止损失守日" value={stats.stopLossDays} />
        <SummaryCard label="过度交易日" value={stats.overtradeDays} />
        <SummaryCard label="开盘30m交易" value={stats.opening30TradeCount} />
        <SummaryCard label="Phase2 未通过" value={stats.phase2CheckFailCount} />
        <SummaryCard label="过滤未过" value={stats.certificateFilterFailCount} />
        <SummaryCard label="异常交易数" value={stats.abnormalTradeCount} />
      </div>
      <div className="mt-4 grid gap-3">
        <ListCard items={stats.topSetups.map((item) => `${item.label} · ${item.count}`)} title="高频形态" />
        <ListCard items={stats.topActivePlans.map((item) => `${item.label} · ${item.count}`)} title="高频计划" />
        <ListCard items={stats.topActiveSetups.map((item) => `${item.label} · ${item.count}`)} title="高频主练形态" />
        <ListCard items={stats.recentIssues.map((item) => `${formatTradeDate(item.tradeDate)} · ${item.note}`)} title="最近问题" />
        <ListCard items={stats.recentFixes.map((item) => `${formatTradeDate(item.tradeDate)} · ${item.note}`)} title="最近修正" />
        <ListCard items={stats.recentNoTradeNotes.map((item) => `${formatTradeDate(item.tradeDate)} · ${item.note}`)} title="最近空仓说明" />
      </div>
    </section>
  )
}

function RecentListsSection({ workspace }: { workspace: WorkspaceOverview }) {
  return (
    <section className="tt-card p-5">
      <div>
        <h3 className="font-body text-lg font-semibold text-toptrader-ink">最近入口</h3>
        <p className="mt-1 text-[13px] text-toptrader-muted">先把最近记录和最近产物清单都放出来，作为切换与追踪入口。</p>
      </div>
      <div className="mt-4 grid gap-3">
        <ListCard
          items={workspace.state.recentRecords.map((item) => `${formatTradeDate(item.tradeDate)} · ${displayValue(item.market === 'US' ? 'us_stock_options' : item.tradingMode)} · 交易 ${item.tradeCount} · ${item.closeoutLabel}`)}
          title="最近交易记录"
        />
        <ListCard items={workspace.state.recentCloseouts.map((item) => `${item.title} · ${item.path}`)} title="最近归档草稿" />
        <ListCard items={workspace.state.recentSummaries.map((item) => `${item.title} · ${item.path}`)} title="最近试验总结" />
        <ListCard items={workspace.state.recentAudits.map((item) => `${item.title} · ${item.path}`)} title="最近字段审计" />
      </div>
    </section>
  )
}

function HistoryDetailsSection({
  history,
  onSelect,
  selectedHistoryDay,
  selectedHistoryError,
  selectedHistoryLoading,
  selectedHistoryPath,
}: {
  history: HistoryOverview
  onSelect: (path: string) => void
  selectedHistoryDay: DailyRecord | null
  selectedHistoryError: string
  selectedHistoryLoading: boolean
  selectedHistoryPath: string
}) {
  return (
    <section className="tt-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-2.5">
        <div>
          <h3 className="font-body text-lg font-semibold text-toptrader-ink">历史交易日表</h3>
          <p className="mt-1 text-[13px] text-toptrader-muted">把 `ReviewHubDayRow` 返回的细字段尽量完整展示，并可点开只读详情。</p>
        </div>
        <Badge label={`${history.days.length} 个交易日`} />
      </div>
      <div className="mt-3 overflow-x-auto">
        <table className="tt-table min-w-full text-left text-[13px]">
          <thead>
            <tr>
              <th>日期</th>
              <th>模式</th>
              <th>交易</th>
              <th>盈亏</th>
              <th>计划/形态</th>
              <th>质量</th>
              <th>查看</th>
            </tr>
          </thead>
          <tbody>
            {history.days.map((row) => (
              <tr key={row.path}>
                <td className="px-3 py-3">
                  <div className="font-medium text-toptrader-accent">{formatTradeDate(row.tradeDate)}</div>
                  <div className="text-xs text-toptrader-muted">{row.day} / {displayValue(row.market)}</div>
                </td>
                <td className="px-3 py-3 text-toptrader-muted">
                  <div>{displayValue(row.market === 'US' ? 'us_stock_options' : row.tradingMode)}</div>
                  <div className="text-xs">{row.state}</div>
                </td>
                <td className="px-3 py-3 text-toptrader-muted">
                  <div>{row.tradeCount} 笔</div>
                  <div className="text-xs">赢{row.winCount} / 亏{row.lossCount} / 平{row.breakevenCount}</div>
                </td>
                <td className="px-3 py-3 text-toptrader-muted">
                  <div>{formatHkdSummaryAmount(row.pnlValue)}</div>
                  <div className="text-xs">违规 {row.violationCount}</div>
                </td>
                <td className="px-3 py-3 text-toptrader-muted">
                  <div>{displayValue(row.activePlan)}</div>
                  <div className="text-xs">{displayValue(row.activeSetup)}</div>
                </td>
                <td className="px-3 py-3 text-toptrader-muted">
                  <div>{row.qualityIssues.length ? row.qualityIssues.join(' / ') : '无明显问题'}</div>
                  <div className="text-xs">归档 {row.closeoutLabel}</div>
                </td>
                <td className="px-3 py-3">
                  <button className="tt-secondary px-2.5 py-1.5 text-[11px] font-bold" onClick={() => onSelect(row.path)} type="button">
                    查看
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ReadonlyDayDetail
        day={selectedHistoryDay}
        error={selectedHistoryError}
        loading={selectedHistoryLoading}
        selectedRecordPath={selectedHistoryPath}
      />
    </section>
  )
}

function ArtifactCard({ artifact, title }: { artifact: ArtifactPreview; title: string }) {
  return (
    <SectionCard title={title}>
      <div className="space-y-3">
        <MetaGrid
          items={[
            ['是否存在', boolText(artifact.exists)],
            ['标题', artifact.title || '--'],
            ['路径', artifact.path || '--'],
          ]}
        />
        <MarkdownPreview content={artifact.preview || ''} emptyText="暂无产物预览。" />
      </div>
    </SectionCard>
  )
}

function DiagnosticStatusCard({
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
    <div className="rounded-xl border border-toptrader-line bg-toptrader-panel px-4 py-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-semibold text-toptrader-accent">{title}</div>
        <Badge label={label} tone={tone} />
      </div>
      <p className="mt-2 text-[13px] leading-5 text-toptrader-muted">{action}</p>
      <div className="mt-3 space-y-2">
        {details.length ? details.map((item) => (
            <div key={item} className="rounded-lg border border-toptrader-line bg-toptrader-soft/35 px-3 py-2 text-[13px] text-toptrader-ink">
            {item}
          </div>
        )) : (
          <div className="rounded-lg border border-dashed border-toptrader-line bg-toptrader-soft/25 px-3 py-2 text-[13px] text-toptrader-muted">
            暂无补充说明。
          </div>
        )}
      </div>
    </div>
  )
}

function ListCard({ items, title }: { items: string[]; title: string }) {
  return (
    <SectionCard title={title}>
      {items.length ? (
        <div className="space-y-2">
          {items.map((item, index) => (
            <div key={`${title}-${index}`} className="rounded-lg border border-toptrader-line bg-toptrader-soft/30 px-3 py-2 text-[13px] text-toptrader-ink">
              {item}
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-toptrader-line bg-toptrader-soft/20 px-3 py-2 text-[13px] text-toptrader-muted">
          暂无数据。
        </div>
      )}
    </SectionCard>
  )
}

function SectionCard({
  children,
  className = '',
  title,
}: {
  children: ReactNode
  className?: string
  title: string
}) {
  return (
    <section className={['tt-bento-panel', className].join(' ')}>
      <h4 className="font-body text-sm font-semibold text-toptrader-ink">{title}</h4>
      <div className="mt-3">{children}</div>
    </section>
  )
}

function MetaGrid({ items }: { items: Array<[string, string]> }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {items.map(([label, value]) => (
        <MetaRow key={`${label}-${value}`} label={label} value={value} />
      ))}
    </div>
  )
}

function EmptyCurrentDaySection() {
  return (
    <section className="tt-card p-5 text-sm text-toptrader-muted">
      当前没有载入交易日，因此全量数据台暂时只显示 workspace / artifacts / history 维度。
    </section>
  )
}

function boolText(value: boolean) {
  return value ? '是' : '否'
}

function nullableBoolText(value: boolean | null) {
  if (value === null) return '--'
  return boolText(value)
}

function stringify(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return '--'
  return String(value)
}

function statusTone(status: string): 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'ready' || status === 'normal' || status === 'open') return 'success'
  if (status === 'blocked' || status === 'stop' || status === 'locked') return 'danger'
  if (status === 'observe_only' || status === 'cooldown' || status === 'protect_profit' || status === 'caution') return 'warning'
  return 'neutral'
}

function buildHistoryQuery(window?: string, sampleFilter?: string) {
  const params = new URLSearchParams()
  if (window) params.set('window', window)
  if (sampleFilter) params.set('sampleFilter', sampleFilter)
  const query = params.toString()
  return query ? `?${query}` : ''
}
