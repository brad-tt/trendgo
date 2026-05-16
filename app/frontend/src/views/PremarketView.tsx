import { AgentSessionPanel } from '../components/agent/AgentSessionPanel'
import { StaticRuleCard } from '../components/workbench/StaticRuleCard'
import { Badge } from '../components/ui/Badge'
import { MetaRow } from '../components/ui/MetaRow'
import { SHARED_NO_TRADE_RULES, SHARED_STOP_RULES } from '../components/workbench/workbenchPresets'
import { useWorkspaceData } from '../hooks/useWorkspaceData'
import { useWorkspace } from '../contexts/WorkspaceContext'
import { displayValue, formatTradeDate } from '../utils/display'
import { WorkbenchView } from './WorkbenchView'
import { useState } from 'react'
import type { ToastState } from '../components/Toast'
import { Toast } from '../components/Toast'

export function PremarketView() {
  const { day, setDay } = useWorkspaceData()
  const { state } = useWorkspace()
  const [toast, setToast] = useState<ToastState | null>(null)
  const closeout = day?.closeout
  const validation = day?.validation
  const isUsMode = day?.workbench.tradingMode === 'us_stock_options'
  const closureSteps = [
    {
      done: validation?.preMarketDone ?? false,
      helper: '盘前 checklist / 作战台',
      label: '盘前完成',
    },
    {
      done: validation?.intradayRecordComplete ?? false,
      helper: '交易与纪律事件已补齐',
      label: '盘中记录',
    },
    {
      done: validation?.postMarketReviewDone ?? false,
      helper: '复盘字段已完成',
      label: '盘后复盘',
    },
    {
      done: Boolean(closeout?.exists) && !closeout?.stale,
      helper: closeout?.exists ? '归档草稿已同步' : '尚未生成归档草稿',
      label: '归档同步',
    },
  ]
  const completedSteps = closureSteps.filter((step) => step.done).length
  const progressPercent = Math.round((completedSteps / closureSteps.length) * 100)
  const closeoutLabel = closeout?.exists ? (closeout.stale ? '需更新' : '已生成') : '未生成'
  const progressToneClass =
    progressPercent === 100 ? 'bg-emerald-500' : progressPercent >= 50 ? 'bg-amber-500' : 'bg-slate-400'
  const capitalUsedText = day?.workbench.capitalUsed === null || day?.workbench.capitalUsed === undefined ? '--' : String(day.workbench.capitalUsed)
  const profitTargetText = day?.workbench.profitTargetPct === null || day?.workbench.profitTargetPct === undefined ? '--' : `${day.workbench.profitTargetPct}%`
  const keyReminderText = day?.preMarket.keyReminder || '--'
  const marketFocusLabel = isUsMode ? '主看股票池' : '关键位'
  const marketFocusValue = day
    ? isUsMode
      ? day.playbook.focusTickers || day.workbench.usWatchlist || '--'
      : `${day.workbench.upperPressure || '--'} / ${day.workbench.lowerSupport || '--'}`
    : '--'
  const executionConclusion = day
    ? isUsMode
      ? day.playbook.optionEntrySignal || day.playbook.optionRiskPlan || '先补期权入场和风控计划'
      : day.playbook.open30KeySignal || day.playbook.abnormalPlan || '先补开盘 30 分钟信号和异常预案'
    : '--'
  const corePlanItems = day
    ? isUsMode
      ? [
          ['期权时段计划', displayValue(day.playbook.optionSessionPlan)],
          ['期权主练形态', displayValue(day.playbook.optionFocusSetup)],
          ['主看股票池', day.playbook.focusTickers || '--'],
          ['期权入场信号', day.playbook.optionEntrySignal || '--'],
          ['期权合约过滤', day.playbook.optionContractFilter || '--'],
          ['期权风控计划', day.playbook.optionRiskPlan || '--'],
          ['事件风险预案', day.playbook.optionEventRiskPlan || '--'],
        ]
      : [
          ['开盘计划', displayValue(day.playbook.openingPlan)],
          ['主练形态', displayValue(day.playbook.focusSetup)],
          ['开盘 30 分钟信号', day.playbook.open30KeySignal || '--'],
          ['牛熊证过滤提醒', day.playbook.certificateFilterNote || '--'],
          ['异常场景预案', day.playbook.abnormalPlan || '--'],
          ['上方压力 / 下方支撑', `${day.workbench.upperPressure || '--'} / ${day.workbench.lowerSupport || '--'}`],
        ]
    : []
  const supportingItems = day
    ? [
        ['盘前状态', displayValue(day.preMarket.state)],
        ['是否遵守常规规则', day.preMarket.followNormalRules ? '是' : '否'],
        ['盘前备注', day.preMarket.note || '--'],
        ['港股观察列表', day.workbench.hkWatchlist || '--'],
        ['美股观察列表', day.workbench.usWatchlist || '--'],
      ]
    : []

  return (
    <div className="space-y-3.5">
      <Toast onClear={() => setToast(null)} toast={toast} />
      {state ? (
        <AgentSessionPanel
          currentMarket={state.currentMarket === 'US' ? 'US' : 'HK'}
          currentTradeDate={day?.base.tradeDate || state.currentTradeDate}
          onCommitted={(nextDay) => setDay(nextDay)}
          onToast={setToast}
        />
      ) : null}
      <div className="tt-bento-grid items-start">
        <div className="col-span-12 xl:col-span-9">
          {day ? (
            <section className="tt-bento-panel">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="tt-heading-card">盘前决策面板</h3>
                  <p className="mt-1 text-xs leading-5 text-toptrader-muted">
                    第一眼只看今天能不能做、用多少钱、目标是什么、核心执行依据是什么。
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge label={formatTradeDate(day.base.tradeDate)} tone="success" />
                  <Badge label={displayValue(day.base.market)} />
                  <Badge label={displayValue(day.workbench.tradingMode)} />
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <DecisionSignalCard helper={displayValue(day.workbench.mainDirection)} label="今天是否交易" tone={day.preMarket.tradingToday ? 'success' : 'warning'} value={day.preMarket.tradingToday ? '交易' : '不交易'} />
                <DecisionSignalCard helper={displayValue(day.workbench.currentState)} label="当前状态" value={displayValue(day.preMarket.state)} />
                <DecisionSignalCard emphasis label="使用本金" value={capitalUsedText} />
                <DecisionSignalCard emphasis label="盈利目标" value={profitTargetText} />
                <DecisionSignalCard helper={isUsMode ? '美股期权' : '恒指牛熊证'} label={marketFocusLabel} value={marketFocusValue} />
              </div>

              <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,0.82fr)_minmax(0,1.18fr)]">
                <section className="rounded-lg border border-toptrader-line bg-toptrader-soft/35 px-3 py-3">
                  <div className="text-[11px] font-semibold tracking-[0.08em] text-toptrader-muted">今日执行结论</div>
                  <div className="mt-3 grid gap-2.5">
                    <MetaRow label="关键提醒" value={keyReminderText} />
                    <MetaRow label={isUsMode ? '期权执行依据' : '开盘执行依据'} value={executionConclusion} />
                    <MetaRow label="主方向" value={displayValue(day.workbench.mainDirection)} />
                    <MetaRow label="是否遵守常规规则" value={day.preMarket.followNormalRules ? '是' : '否'} />
                  </div>
                </section>

                <section className="rounded-lg border border-toptrader-line bg-toptrader-panel px-3 py-3">
                  <div className="text-[11px] font-semibold tracking-[0.08em] text-toptrader-muted">
                    {isUsMode ? '美股期权专项计划' : '港股执行计划'}
                  </div>
                  <div className="mt-3 grid gap-2.5 md:grid-cols-2">
                    {corePlanItems.map(([label, value]) => (
                      <MetaRow key={label} label={label} value={value} />
                    ))}
                  </div>
                </section>
              </div>

              <section className="mt-4 rounded-lg border border-toptrader-line bg-toptrader-panel/88 px-3 py-3">
                <div className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-3">
                  {supportingItems.map(([label, value]) => (
                    <MetaRow key={label} label={label} value={value} />
                  ))}
                </div>
              </section>
            </section>
          ) : null}

          <WorkbenchView />
        </div>

        <aside className="col-span-12 space-y-3 xl:sticky xl:top-24 xl:col-span-3">
          <section className="tt-bento-panel">
            <div>
              <h3 className="tt-heading-card">纪律护栏</h3>
              <p className="mt-1 text-[11px] leading-4 text-toptrader-muted">原则性约束保持常驻可见，盘前到盘中都不藏。</p>
            </div>
            <div className="mt-3 space-y-3">
              <StaticRuleCard
                accentClassName="from-toptrader-panel via-amber-900/15 to-toptrader-panel"
                compact
                helper="出现以下情况时，不开新仓，先退回观察。"
                items={SHARED_NO_TRADE_RULES}
                title="禁做场景"
              />
              <StaticRuleCard
                accentClassName="from-toptrader-panel via-toptrader-rose/10 to-toptrader-panel"
                compact
                helper="触发以下条件时，直接暂停或结束当天交易。"
                items={SHARED_STOP_RULES}
                title="应停止条件"
              />
            </div>
          </section>
        </aside>
      </div>

      <section className="tt-bento-panel">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="tt-heading-card">流程状态</h3>
            <p className="mt-1 text-xs leading-5 text-toptrader-muted">
              这里只看全流程是否走完，不在这里操作。已完成 {completedSteps} / {closureSteps.length}，当前进度 {progressPercent}%。
            </p>
          </div>
          <span className="rounded-full border border-toptrader-line bg-toptrader-panel px-2.5 py-1 text-[11px] font-semibold text-toptrader-ink">
            归档 {closeoutLabel}
          </span>
        </div>
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-toptrader-soft/70">
          <div
            className={['h-full rounded-full transition-all', progressToneClass].join(' ')}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {closureSteps.map((step) => (
            <CompactProgressRow key={step.label} done={step.done} helper={step.helper} label={step.label} />
          ))}
        </div>
      </section>
    </div>
  )
}

function CompactProgressRow({
  done,
  helper,
  label,
}: {
  done: boolean
  helper: string
  label: string
}) {
  return (
    <div className="rounded-lg border border-toptrader-line bg-toptrader-panel/92 px-3 py-2.5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[12px] font-medium text-toptrader-accent">{label}</p>
        <span
          className={[
            'rounded-full px-2 py-0.5 text-[10px] font-semibold',
            done ? 'bg-toptrader-brand text-toptrader-mist' : 'bg-toptrader-soft text-toptrader-muted',
          ].join(' ')}
        >
          {done ? '完成' : '待办'}
        </span>
      </div>
      <p className="mt-1.5 text-[11px] leading-4 text-toptrader-muted">{helper}</p>
    </div>
  )
}

function DecisionSignalCard({
  emphasis = false,
  helper,
  label,
  tone = 'neutral',
  value,
}: {
  emphasis?: boolean
  helper?: string
  label: string
  tone?: 'neutral' | 'success' | 'warning'
  value: string
}) {
  const toneClass =
    tone === 'success'
      ? 'border-emerald-500/25 bg-emerald-500/8'
      : tone === 'warning'
        ? 'border-amber-500/25 bg-amber-500/8'
        : 'border-toptrader-line bg-toptrader-panel'
  return (
    <div className={['rounded-lg border px-3 py-3 shadow-sm', toneClass, emphasis ? 'ring-1 ring-inset ring-toptrader-brand/12' : ''].join(' ')}>
      <p className="text-[10px] font-semibold tracking-[0.08em] text-toptrader-muted">{label}</p>
      <p className={['mt-1 leading-5 text-toptrader-ink', emphasis ? 'text-[18px] font-bold' : 'text-[14px] font-semibold'].join(' ')}>{value}</p>
      {helper ? <p className="mt-1 text-[10px] leading-4 text-toptrader-muted">{helper}</p> : null}
    </div>
  )
}
