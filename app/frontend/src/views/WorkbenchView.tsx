import { useEffect, useMemo, useState } from 'react'

import { Drawer } from '../components/Drawer'
import { Toast, type ToastState } from '../components/Toast'
import { Field } from '../components/ui/Field'
import { ToggleRow } from '../components/ui/ToggleRow'
import { ReferenceInputsPanel } from '../components/workbench/ReferenceInputsPanel'
import { buildWorkbenchPayload } from '../components/workbench/saveWorkbenchPayload'
import { normalizeWatchlist } from '../components/workbench/watchlist'
import {
  createWorkbenchForm,
  formatTodayTradeDate,
  hsiPlaybookPresets,
  SHARED_NO_TRADE_RULES,
  SHARED_STOP_RULES,
  usPlaybookPresets,
  type WorkbenchFormState,
} from '../components/workbench/workbenchPresets'
import { useWorkspaceData } from '../hooks/useWorkspaceData'
import type { DayActionResponse } from '../types'
import { apiClient } from '../utils/apiClient'
import { displayValue, formatTradeDate } from '../utils/display'

const inputClassName = 'tt-input'
const selectClassName = inputClassName
const textareaClassName = 'tt-input leading-5'

type WorkbenchStep = 'step1' | 'step2' | 'step3' | 'step4'

export function WorkbenchView() {
  const { day, error, loading, refresh, setDay, state } = useWorkspaceData()
  const [form, setForm] = useState<WorkbenchFormState | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [isStartingToday, setIsStartingToday] = useState(false)
  const [activeStep, setActiveStep] = useState<WorkbenchStep | null>(null)
  const [toast, setToast] = useState<ToastState | null>(null)

  useEffect(() => {
    let active = true
    queueMicrotask(() => {
      if (!active) return
      setForm(day ? createWorkbenchForm(day) : null)
    })
    return () => {
      active = false
    }
  }, [day])

  const isUsMode = form?.tradingMode === 'us_stock_options'
  const initialForm = useMemo(() => (day ? createWorkbenchForm(day) : null), [day])
  const todayTradeDate = useMemo(() => formatTodayTradeDate(), [])
  const currentTradeDate = day?.base.tradeDate || state?.currentTradeDate || ''
  const currentMarket = state?.currentMarket === 'US' ? 'US' : 'HK'
  const hasTodayRecordForCurrentMarket = state?.todayRecords?.[currentMarket] ?? false
  const hasAnyRecordForCurrentMarket = Boolean(state?.recentRecords.length)
  const needsTodayRecord = !hasTodayRecordForCurrentMarket || currentTradeDate !== todayTradeDate
  const isDirty = useMemo(() => {
    if (!form || !initialForm) return false
    return JSON.stringify(form) !== JSON.stringify(initialForm)
  }, [form, initialForm])
  const stepReady = useMemo(() => {
    if (!form) {
      return { step1: false, step2: false, step3: false }
    }
    const noTradeMode = !form.tradingToday
    const step1 =
      form.mainDirection !== 'undecided' &&
      form.currentState !== 'unset' &&
      Boolean(form.preMarketState)
    const step2 = Boolean(form.keyReminder.trim())
    const step3 = noTradeMode
      ? true
      : isUsMode
      ? Boolean(
          form.optionSessionPlan &&
            form.focusTickers.trim() &&
            form.optionFocusSetup &&
            form.optionEntrySignal.trim() &&
            form.optionContractFilter.trim() &&
            form.optionRiskPlan.trim() &&
            form.optionEventRiskPlan.trim(),
        )
      : Boolean(
          form.openingPlan &&
            form.focusSetup &&
            form.open30KeySignal.trim() &&
            form.certificateFilterNote.trim() &&
          form.abnormalPlan.trim(),
        )
    const step4 = noTradeMode
      ? true
      : Boolean(
      form.capitalUsed.trim() &&
        form.profitTargetPct.trim() &&
        (form.hkWatchlist.trim() || form.usWatchlist.trim()),
      )
    return { step1, step2, step3, step4 }
  }, [form, isUsMode])

  const updateField = <K extends keyof WorkbenchFormState>(key: K, value: WorkbenchFormState[K]) => {
    setForm((current) => (current ? { ...current, [key]: value } : current))
  }

  const normalizeWatchlistField = (key: 'hkWatchlist' | 'usWatchlist') => {
    setForm((current) => {
      if (!current) return current
      return {
        ...current,
        [key]: normalizeWatchlist(current[key]),
      }
    })
  }

  const applyPreset = (presetKey: keyof typeof usPlaybookPresets | keyof typeof hsiPlaybookPresets) => {
    if (!form) return
    if (isUsMode) {
      const preset = usPlaybookPresets[presetKey as keyof typeof usPlaybookPresets]
      if (!preset) return
      setForm((current) => (current ? { ...current, ...preset } : current))
      return
    }
    const preset = hsiPlaybookPresets[presetKey as keyof typeof hsiPlaybookPresets]
    if (!preset) return
    setForm((current) => (current ? { ...current, ...preset } : current))
  }

  const save = async (options?: { closeAfterSave?: boolean }) => {
    if (!day || !form) return
    setIsSaving(true)
    try {
      const response = await apiClient.put<DayActionResponse>('/api/day-records/workbench', {
        ...buildWorkbenchPayload(form),
        market: day.base.market,
        tradeDate: day.base.tradeDate,
      })
      setDay(response.day)
      setToast({ message: response.message, tone: 'success' })
      await refresh()
      if (options?.closeAfterSave) {
        setActiveStep(null)
      }
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : '保存作战台失败。',
        tone: 'error',
      })
    } finally {
      setIsSaving(false)
    }
  }

  const startTodayDay = async () => {
    const tradingMode = currentMarket === 'US' ? 'us_stock_options' : 'hsi_bull_bear_certificate'
    const currentState = form?.currentState === 'unset' ? 'normal' : form?.currentState || 'normal'
    const focus = form?.focusTickers.trim() || form?.open30KeySignal.trim() || form?.keyReminder.trim() || ''
    setIsStartingToday(true)
    try {
      const response = await apiClient.post<DayActionResponse>('/api/days', {
        currentState,
        focus,
        tradeDate: todayTradeDate,
        tradingMode,
      })
      setDay(response.day)
      setToast({ message: `${response.message} 已切换到今天 ${formatTradeDate(todayTradeDate)}。`, tone: 'success' })
      await refresh()
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : '创建今天交易日失败。',
        tone: 'error',
      })
    } finally {
      setIsStartingToday(false)
    }
  }

  if (loading && !day) {
    return <WorkbenchPlaceholder text="正在加载作战台…" />
  }

  if (!day) {
    if (!state) {
      return <WorkbenchPlaceholder text={error || '当前没有可编辑交易日。'} />
    }
    return (
      <>
        <Toast onClear={() => setToast(null)} toast={toast} />
        <section className="tt-bento-panel accent col-span-12 rounded-[20px] border-amber-500/30 bg-gradient-to-r from-toptrader-panel via-amber-900/15 to-toptrader-panel p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-xs font-black uppercase tracking-[0.18em] text-amber-400">当前未载入</div>
              <h3 className="mt-2 tt-heading-page">
                {hasAnyRecordForCurrentMarket
                  ? `当前没有载入可编辑的${currentMarket === 'HK' ? '港股' : '美股'}工作台`
                  : `当前还没有${currentMarket === 'HK' ? '港股' : '美股'}工作台`}
              </h3>
              <p className="tt-callout-copy mt-2 text-xs leading-5">
                现在可以直接创建并切到 {formatTradeDate(todayTradeDate)} 的{currentMarket === 'HK' ? '港股' : '美股'}工作台。
                {hasAnyRecordForCurrentMarket && currentTradeDate
                  ? ` 当前工作区日期是 ${formatTradeDate(currentTradeDate)}。`
                  : ''}
              </p>
            </div>
            <button
              className="tt-contrast-action px-4 py-2.5 text-xs font-black disabled:cursor-not-allowed"
              disabled={isStartingToday}
              onClick={() => void startTodayDay()}
              type="button"
            >
              {isStartingToday
                ? `正在创建今天的${currentMarket === 'HK' ? '港股' : '美股'}工作台…`
                : `创建并切到今天的${currentMarket === 'HK' ? '港股' : '美股'}工作台 (${formatTradeDate(todayTradeDate)})`}
            </button>
          </div>
        </section>
        {error ? (
          <p className="mt-3 rounded-lg border border-toptrader-rose/30 bg-toptrader-rose/10 px-3 py-2.5 text-xs text-toptrader-rose">
            {error}
          </p>
        ) : null}
      </>
    )
  }

  if (!form) {
    return <WorkbenchPlaceholder text="正在加载作战台…" />
  }

  const stepCards = [
    {
      helper: `${form.tradingToday ? '今天交易' : '今天不交易'} / ${displayValue(form.tradingMode)} / ${displayValue(form.mainDirection)}`,
      id: 'step1' as const,
      label: '今日状态',
      ready: stepReady.step1,
      summary: `${displayValue(form.preMarketState)} / ${displayValue(form.currentState)}`,
    },
    {
      helper: form.keyReminder.trim() || '先写一句今天最重要的提醒。',
      id: 'step2' as const,
      label: '关键提醒',
      ready: stepReady.step2,
      summary: form.preMarketNote.trim() || '可补盘前备注',
    },
    {
      helper: !form.tradingToday
        ? '今天不交易，专项计划不作为必填。'
        : isUsMode
        ? `${displayValue(form.optionSessionPlan)} / ${displayValue(form.optionFocusSetup)}`
        : `${displayValue(form.openingPlan)} / ${displayValue(form.focusSetup)}`,
      id: 'step3' as const,
      label: isUsMode ? '美股期权专项' : '恒指牛熊证专项',
      ready: stepReady.step3,
      summary: isUsMode
        ? (!form.tradingToday ? '空仓日模式' : form.focusTickers.trim() || '先确定主看股票池')
        : (!form.tradingToday ? '空仓日模式' : form.open30KeySignal.trim() || '先写开盘 30 分钟关键信号'),
    },
    {
      helper: !form.tradingToday
        ? '今天不交易，观察池与高级项只作记录参考。'
        : `${form.hkWatchlist.trim() ? '港股池已写' : '港股池未写'} / ${form.usWatchlist.trim() ? '美股池已写' : '美股池未写'}`,
      id: 'step4' as const,
      label: '观察池与资金',
      ready: stepReady.step4,
      summary: !form.tradingToday ? '空仓日模式' : `${form.capitalUsed || '--'} / ${form.profitTargetPct || '--'}%`,
    },
  ]

  const drawerTitle =
    activeStep === 'step1'
      ? '今日状态'
      : activeStep === 'step2'
        ? '关键提醒'
        : activeStep === 'step3'
          ? isUsMode
            ? '美股期权专项'
            : '恒指牛熊证专项'
          : activeStep === 'step4'
            ? '观察池与资金'
          : ''

  return (
    <>
      <Toast onClear={() => setToast(null)} toast={toast} />
      <section className="space-y-3.5">
        {!form.tradingToday ? (
          <section className="tt-bento-panel accent col-span-12 rounded-[20px] border-sky-500/30 bg-gradient-to-r from-toptrader-panel via-sky-900/10 to-toptrader-panel p-4">
            <div className="text-xs font-black uppercase tracking-[0.18em] text-toptrader-sky">空仓日模式</div>
            <p className="mt-2 text-xs leading-5 text-toptrader-muted">
              盘前已明确设置今天不交易。后续页面会按空仓日流程处理，重点是保留纪律、等待依据和空仓说明，不再按普通交易日要求补完整交易事实。
            </p>
          </section>
        ) : null}
        {needsTodayRecord ? (
          <section className="tt-bento-panel accent col-span-12 rounded-[20px] border-amber-500/30 bg-gradient-to-r from-toptrader-panel via-amber-900/15 to-toptrader-panel p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-xs font-black uppercase tracking-[0.18em] text-amber-400">今日未切换</div>
                <h3 className="mt-2 tt-heading-page">
                  {hasTodayRecordForCurrentMarket
                    ? `当前作战台还是 ${formatTradeDate(currentTradeDate)}，不是今天`
                    : `当前还没有今天的${currentMarket === 'HK' ? '港股' : '美股'}工作台`}
                </h3>
                <p className="tt-callout-copy mt-2 text-xs leading-5">
                  如果你现在要录入 {formatTradeDate(todayTradeDate)} 的盘前计划，先创建并切换到今天的{currentMarket === 'HK' ? '港股' : '美股'}工作台，顶部状态和其他页面会一起同步。
                </p>
              </div>
              <button
                className="tt-contrast-action px-4 py-2.5 text-xs font-black disabled:cursor-not-allowed"
                disabled={isStartingToday}
                onClick={() => void startTodayDay()}
                type="button"
              >
                {isStartingToday
                  ? `正在创建今天的${currentMarket === 'HK' ? '港股' : '美股'}工作台…`
                  : `创建并切到今天的${currentMarket === 'HK' ? '港股' : '美股'}工作台 (${formatTradeDate(todayTradeDate)})`}
              </button>
            </div>
          </section>
        ) : null}

        <div className="tt-bento-grid">
          <section className="col-span-12 rounded-lg border border-toptrader-line bg-toptrader-panel/82 px-3 py-3 shadow-sm">
            <div className="flex flex-wrap items-center gap-2.5">
              <div className="mr-auto min-w-[132px]">
                <h2 className="text-[15px] font-black tracking-tight text-toptrader-ink">盘前作战台</h2>
                <p className="mt-0.5 text-[11px] leading-4 text-toptrader-muted">点开模块编辑，保存后收起。</p>
              </div>

              {stepCards.map((step) => (
                <button
                  key={step.id}
                  className="inline-flex min-h-[42px] min-w-[128px] items-center justify-between gap-2 rounded-md border border-toptrader-line bg-toptrader-soft/24 px-2.5 py-2 text-left transition hover:border-toptrader-brand/40 hover:bg-toptrader-brand/6"
                  onClick={() => setActiveStep(step.id)}
                  type="button"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-[12px] font-bold text-toptrader-accent">{step.label}</span>
                    <span className="block max-w-[128px] truncate text-[10px] text-toptrader-muted">{step.summary}</span>
                  </span>
                  <span
                    className={[
                      'shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold',
                      step.ready ? 'bg-toptrader-brand text-toptrader-mist' : 'bg-amber-500/12 text-amber-400',
                    ].join(' ')}
                  >
                    {step.ready ? '已填' : '待补'}
                  </span>
                </button>
              ))}

              <button
                className="tt-primary ml-auto px-4 py-2 text-[11px] font-bold disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isSaving || !isDirty}
                onClick={() => void save({ closeAfterSave: true })}
                type="button"
              >
                {isSaving ? '保存中…' : isDirty ? '保存并收起' : '暂无改动'}
              </button>
            </div>

            {error ? (
              <p className="mt-3 rounded-lg border border-toptrader-rose/30 bg-toptrader-rose/10 px-3 py-2.5 text-xs text-toptrader-rose">
                {error}
              </p>
            ) : null}
          </section>

        </div>
      </section>

      <Drawer
        headerAction={
          <div className="flex items-center gap-2">
            <button
              className="tt-secondary px-3 py-1.5 text-xs font-bold"
              onClick={() => setActiveStep(null)}
              type="button"
            >
              取消
            </button>
            <button
              className="tt-primary px-3 py-1.5 text-xs font-bold disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isSaving || !isDirty}
              onClick={() => void save({ closeAfterSave: true })}
              type="button"
            >
              {isSaving ? '保存中…' : '保存并收起'}
            </button>
          </div>
        }
        isOpen={activeStep !== null}
        onClose={() => setActiveStep(null)}
        title={drawerTitle}
      >
        {activeStep === 'step1' ? (
          <div className="grid gap-3">
            <div className="rounded-lg border border-toptrader-line bg-toptrader-soft/25 px-3 py-3 text-xs leading-5 text-toptrader-muted">
              先决定今天做不做、用什么模式、主方向是什么。这里只处理最前面的决策条件。
            </div>
            <div className="grid gap-2.5">
              <ToggleRow checked={form.tradingToday} label="今天交易" onChange={(checked) => updateField('tradingToday', checked)} />
              <ToggleRow checked={form.followNormalRules} label="遵守常规规则" onChange={(checked) => updateField('followNormalRules', checked)} />
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <Field label="模式">
                <select className={selectClassName} onChange={(event) => updateField('tradingMode', event.target.value)} value={form.tradingMode}>
                  <option value="hsi_bull_bear_certificate">恒指牛熊证</option>
                  <option value="us_stock_options">美股期权</option>
                </select>
              </Field>
              <Field label="当日主方向">
                <select className={selectClassName} onChange={(event) => updateField('mainDirection', event.target.value)} value={form.mainDirection}>
                  <option value="undecided">未定</option>
                  <option value="long">做多</option>
                  <option value="short">做空</option>
                  <option value="observe">观察</option>
                </select>
              </Field>
              <Field label="盘前状态">
                <select className={selectClassName} onChange={(event) => updateField('preMarketState', event.target.value)} value={form.preMarketState}>
                  <option value="normal">正常</option>
                  <option value="tired">疲惫</option>
                  <option value="irritated">烦躁</option>
                  <option value="sleep_poor">睡眠差</option>
                  <option value="unstable">状态不稳</option>
                  <option value="other">其他</option>
                </select>
              </Field>
              <Field label="当前状态">
                <select className={selectClassName} onChange={(event) => updateField('currentState', event.target.value)} value={form.currentState}>
                  <option value="unset">未设</option>
                  <option value="stable">稳定</option>
                  <option value="impatient">偏急</option>
                  <option value="defiant">顶撞</option>
                  <option value="tired">疲惫</option>
                  <option value="unfit">不适合交易</option>
                </select>
              </Field>
            </div>
          </div>
        ) : null}

        {activeStep === 'step2' ? (
          <div className="grid gap-3">
            <div className="rounded-lg border border-toptrader-line bg-toptrader-soft/25 px-3 py-3 text-xs leading-5 text-toptrader-muted">
              这一层只保留一句关键提醒和必要备注，避免盘前判断被过多细节打断。
            </div>
            <Field label="关键提醒">
              <textarea className={textareaClassName} onChange={(event) => updateField('keyReminder', event.target.value)} rows={3} value={form.keyReminder} />
            </Field>
            <Field label="盘前备注">
              <textarea className={textareaClassName} onChange={(event) => updateField('preMarketNote', event.target.value)} rows={4} value={form.preMarketNote} />
            </Field>
          </div>
        ) : null}

        {activeStep === 'step3' ? (
          <div className="grid gap-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="rounded-lg border border-toptrader-line bg-toptrader-soft/25 px-3 py-3 text-xs leading-5 text-toptrader-muted">
                按当前模式填写专项计划，抽屉里保留预设按钮，减少重复录入。
              </div>
              <div className="flex flex-wrap gap-1.5">
                {isUsMode ? (
                  <>
                    <button className="tt-secondary px-2.5 py-1.5 text-[11px] font-bold" onClick={() => applyPreset('first15Trend')} type="button">先等 15 分钟</button>
                    <button className="tt-secondary px-2.5 py-1.5 text-[11px] font-bold" onClick={() => applyPreset('vwapReclaim')} type="button">VWAP 收复</button>
                    <button className="tt-secondary px-2.5 py-1.5 text-[11px] font-bold" onClick={() => applyPreset('defensiveNoTrade')} type="button">防守不做</button>
                  </>
                ) : (
                  <>
                    <button className="tt-secondary px-2.5 py-1.5 text-[11px] font-bold" onClick={() => applyPreset('confirmedBreakout')} type="button">确认突破</button>
                    <button className="tt-secondary px-2.5 py-1.5 text-[11px] font-bold" onClick={() => applyPreset('pullbackConfirm')} type="button">回踩确认</button>
                    <button className="tt-secondary px-2.5 py-1.5 text-[11px] font-bold" onClick={() => applyPreset('observeFirst')} type="button">先观察</button>
                  </>
                )}
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {isUsMode ? (
                <>
                  <Field label="期权时段计划">
                    <select className={selectClassName} onChange={(event) => updateField('optionSessionPlan', event.target.value)} value={form.optionSessionPlan}>
                      <option value="">请选择</option>
                      <option value="wait_first_15m">先等 15 分钟</option>
                      <option value="trend_continuation">趋势延续</option>
                      <option value="pullback_only">只做回踩</option>
                      <option value="breakout_if_confirmed">确认突破</option>
                      <option value="clear_no_trade">不清晰不做</option>
                      <option value="avoid_event_risk">避开事件风险</option>
                    </select>
                  </Field>
                  <Field label="期权主练形态">
                    <select className={selectClassName} onChange={(event) => updateField('optionFocusSetup', event.target.value)} value={form.optionFocusSetup}>
                      <option value="">请选择</option>
                      <option value="orb_continuation">开盘区间突破延续</option>
                      <option value="vwap_reclaim">VWAP 收复</option>
                      <option value="trend_pullback">趋势回踩</option>
                      <option value="support_reversal">支撑反转</option>
                      <option value="failed_breakdown">跌破失败反转</option>
                      <option value="clear_observe">观察</option>
                      <option value="other">其他</option>
                    </select>
                  </Field>
                  <Field className="md:col-span-2" label="主看股票池">
                    <textarea className={textareaClassName} onChange={(event) => updateField('focusTickers', event.target.value)} rows={2} value={form.focusTickers} />
                  </Field>
                  <Field className="md:col-span-2" label="期权入场信号">
                    <textarea className={textareaClassName} onChange={(event) => updateField('optionEntrySignal', event.target.value)} rows={2} value={form.optionEntrySignal} />
                  </Field>
                  <Field className="md:col-span-2" label="期权合约过滤">
                    <textarea className={textareaClassName} onChange={(event) => updateField('optionContractFilter', event.target.value)} rows={2} value={form.optionContractFilter} />
                  </Field>
                  <Field className="md:col-span-2" label="期权风控计划">
                    <textarea className={textareaClassName} onChange={(event) => updateField('optionRiskPlan', event.target.value)} rows={2} value={form.optionRiskPlan} />
                  </Field>
                  <Field className="md:col-span-2" label="事件风险预案">
                    <textarea className={textareaClassName} onChange={(event) => updateField('optionEventRiskPlan', event.target.value)} rows={2} value={form.optionEventRiskPlan} />
                  </Field>
                </>
              ) : (
                <>
                  <Field label="开盘计划">
                    <select className={selectClassName} onChange={(event) => updateField('openingPlan', event.target.value)} value={form.openingPlan}>
                      <option value="">请选择</option>
                      <option value="breakout_if_confirmed">确认突破</option>
                      <option value="pullback_only">回踩确认</option>
                      <option value="observe_first">先观察</option>
                      <option value="clear_no_trade">不清晰不做</option>
                    </select>
                  </Field>
                  <Field label="主练形态">
                    <select className={selectClassName} onChange={(event) => updateField('focusSetup', event.target.value)} value={form.focusSetup}>
                      <option value="">请选择</option>
                      <option value="opening_breakout">开盘突破</option>
                      <option value="pullback_reclaim">回踩确认</option>
                      <option value="clear_observe">观察</option>
                      <option value="other">其他</option>
                    </select>
                  </Field>
                  <Field className="md:col-span-2" label="开盘 30 分钟关键信号">
                    <textarea className={textareaClassName} onChange={(event) => updateField('open30KeySignal', event.target.value)} rows={2} value={form.open30KeySignal} />
                  </Field>
                  <Field className="md:col-span-2" label="牛熊证过滤提醒">
                    <textarea className={textareaClassName} onChange={(event) => updateField('certificateFilterNote', event.target.value)} rows={2} value={form.certificateFilterNote} />
                  </Field>
                  <Field className="md:col-span-2" label="异常场景预案">
                    <textarea className={textareaClassName} onChange={(event) => updateField('abnormalPlan', event.target.value)} rows={2} value={form.abnormalPlan} />
                  </Field>
                </>
              )}
            </div>
          </div>
        ) : null}

        {activeStep === 'step4' ? (
          <ReferenceInputsPanel
            compact
            form={form}
            isUsMode={isUsMode}
            noTradeRules={SHARED_NO_TRADE_RULES}
            onNormalizeWatchlist={normalizeWatchlistField}
            onUpdateField={updateField}
            showRules={false}
            stopRules={SHARED_STOP_RULES}
          />
        ) : null}
      </Drawer>
    </>
  )
}

function WorkbenchPlaceholder({ text }: { text: string }) {
  return <section className="tt-card p-4 text-xs text-toptrader-muted">{text}</section>
}
