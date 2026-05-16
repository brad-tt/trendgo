import { useMemo, useState } from 'react'

import type { DailyRecord, DayActionResponse, ReviewFields } from '../../types'
import { apiClient } from '../../utils/apiClient'
import { formatHkdSummaryAmount } from '../../utils/money'
import { FieldError, ReadonlyTradeValue, ReviewField } from './reviewUi'
import { buildFieldClassName } from './reviewUtils'

interface ReviewFormProps {
  review: ReviewFields
  tradeDate: string
  market: string
  isCurrent: boolean
  onSave: (updatedDay: DailyRecord) => void | Promise<void>
  onSaveAndGenerateCloseout?: (updatedDay: DailyRecord) => void | Promise<void>
}

type ReviewFormState = {
  bestTradeNote: string
  planDeviationLevel: 'none' | 'light' | 'clear'
  planDeviationNote: string
  emotionIssue: string
  executionIssue: string
  marketIssue: string
  maxLossTrade: string
  nextDayOneFix: string
  pnl: string
  riskIssue: string
  setupIssue: string
  tradeCount: string
  winRate: string
  worstTradeNote: string
}

function parseExecutionIssue(value: string) {
  const text = value.trim()
  if (!text) {
    return { level: 'none' as const, note: '' }
  }
  if (text.startsWith('无明显偏离计划')) {
    return { level: 'none' as const, note: text.replace(/^无明显偏离计划[:：]?\s*/, '') }
  }
  if (text.startsWith('轻微偏离计划')) {
    return { level: 'light' as const, note: text.replace(/^轻微偏离计划[:：]?\s*/, '') }
  }
  if (text.startsWith('明显偏离计划')) {
    return { level: 'clear' as const, note: text.replace(/^明显偏离计划[:：]?\s*/, '') }
  }
  return { level: 'clear' as const, note: text }
}

function buildExecutionIssue(level: 'none' | 'light' | 'clear', note: string) {
  const trimmed = note.trim()
  if (level === 'none') {
    return trimmed ? `无明显偏离计划：${trimmed}` : '无明显偏离计划。'
  }
  if (level === 'light') {
    return trimmed ? `轻微偏离计划：${trimmed}` : '轻微偏离计划。'
  }
  return trimmed ? `明显偏离计划：${trimmed}` : '明显偏离计划。'
}

function isMeaningfulReviewText(value: string) {
  const text = value.trim()
  if (!text) {
    return false
  }
  const compact = Array.from(text).filter((char) => /[\p{L}\p{N}]/u.test(char)).join('')
  if (compact.length < 4) {
    return false
  }
  return !/^\d+$/.test(compact)
}

function getReviewErrors(form: ReviewFormState) {
  const errors: Partial<Record<keyof ReviewFormState, string>> = {}
  if (!isMeaningfulReviewText(form.bestTradeNote)) errors.bestTradeNote = '请写清当日最好的动作，至少包含具体事实。'
  if (!isMeaningfulReviewText(form.worstTradeNote)) errors.worstTradeNote = '请写清当日最差的问题或最危险动作。'
  if (!isMeaningfulReviewText(form.emotionIssue)) errors.emotionIssue = '请写清情绪问题或说明当日情绪稳定。'
  if (!isMeaningfulReviewText(form.riskIssue)) errors.riskIssue = '请写清风控问题或说明风控执行情况。'
  if (!isMeaningfulReviewText(form.nextDayOneFix)) errors.nextDayOneFix = '请写明明天只改的一件事。'
  return errors
}

export function ReviewForm({ review, tradeDate, market, isCurrent, onSave, onSaveAndGenerateCloseout }: ReviewFormProps) {
  const parsedExecution = parseExecutionIssue(review.executionIssue)
  const [draft, setDraft] = useState<ReviewFormState>({
    bestTradeNote: review.bestTradeNote,
    planDeviationLevel: parsedExecution.level,
    planDeviationNote: parsedExecution.note,
    emotionIssue: review.emotionIssue,
    executionIssue: review.executionIssue,
    marketIssue: review.marketIssue,
    maxLossTrade: review.maxLossTrade,
    nextDayOneFix: review.nextDayOneFix,
    pnl: review.pnl,
    riskIssue: review.riskIssue,
    setupIssue: review.setupIssue,
    tradeCount: review.tradeCount?.toString() ?? '',
    winRate: review.winRate,
    worstTradeNote: review.worstTradeNote,
  })
  const form = useMemo(
    () => ({
      ...draft,
      pnl: review.pnl,
      tradeCount: review.tradeCount?.toString() ?? '',
      winRate: review.winRate,
    }),
    [draft, review.pnl, review.tradeCount, review.winRate],
  )
  const errors = useMemo(() => getReviewErrors(form), [form])
  const hasErrors = Object.keys(errors).length > 0
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [showExtras, setShowExtras] = useState(false)

  const save = async (options?: { generateCloseout?: boolean }) => {
    setIsSubmitting(true)
    setSubmitError('')
    try {
      const response = await apiClient.put<DayActionResponse>('/api/day-records/review', {
        bestTradeNote: form.bestTradeNote,
        emotionIssue: form.emotionIssue,
        executionIssue: buildExecutionIssue(form.planDeviationLevel, form.planDeviationNote),
        market,
        marketIssue: form.marketIssue,
        maxLossTrade: form.maxLossTrade,
        nextDayOneFix: form.nextDayOneFix,
        pnl: form.pnl,
        riskIssue: form.riskIssue,
        setupIssue: form.setupIssue,
        tradeDate,
        tradeCount: form.tradeCount === '' ? null : Number(form.tradeCount),
        winRate: form.winRate,
        worstTradeNote: form.worstTradeNote,
      })
      if (options?.generateCloseout && onSaveAndGenerateCloseout) {
        await onSaveAndGenerateCloseout(response.day)
      } else {
        await onSave(response.day)
      }
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : '保存复盘失败，请重试。')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="tt-bento p-4 xl:col-span-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="tt-heading-page">盘后复盘</h2>
          <p className="mt-1 text-xs leading-5 text-toptrader-muted">
            盘后先回答 4 个问题：今天最好的一次动作、最大的问题、有没有偏离计划、明天只改哪一件事。
          </p>
        </div>
      </div>
      {hasErrors ? (
        <p className="mt-3 rounded-lg border border-toptrader-rose/30 bg-toptrader-rose/10 px-3 py-2.5 text-xs text-toptrader-rose">
          还差 {Object.keys(errors).length} 个核心问题没写清。
        </p>
      ) : null}
      <div className="mt-3 grid gap-3">
        <ReviewField label="当日盈亏">
          <ReadonlyTradeValue helper="统一折算港币" value={form.pnl || formatHkdSummaryAmount(null)} />
        </ReviewField>
        <ReviewField label="交易数">
          <ReadonlyTradeValue helper="根据当天交易记录自动统计" value={form.tradeCount || '--'} />
        </ReviewField>
        <ReviewField label="胜率">
          <ReadonlyTradeValue helper="保存时自动写入" value={form.winRate || '--'} />
        </ReviewField>
        <ReviewField label="今天最好的一次动作">
          <textarea className={buildFieldClassName(Boolean(errors.bestTradeNote))} onChange={(event) => setDraft((current) => ({ ...current, bestTradeNote: event.target.value }))} rows={2} value={form.bestTradeNote} />
          <FieldError message={errors.bestTradeNote} />
        </ReviewField>
        <ReviewField label="今天最大的一个问题">
          <textarea className={buildFieldClassName(Boolean(errors.worstTradeNote))} onChange={(event) => setDraft((current) => ({ ...current, worstTradeNote: event.target.value }))} rows={2} value={form.worstTradeNote} />
          <FieldError message={errors.worstTradeNote} />
        </ReviewField>
        <ReviewField label="今天有没有明显偏离计划">
          <select
            className={buildFieldClassName(false)}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                planDeviationLevel: event.target.value as 'none' | 'light' | 'clear',
              }))
            }
            value={form.planDeviationLevel}
          >
            <option value="none">没有</option>
            <option value="light">轻微</option>
            <option value="clear">明显</option>
          </select>
        </ReviewField>
        <ReviewField label="偏离计划补充说明（可选）">
          <textarea className={buildFieldClassName(false)} onChange={(event) => setDraft((current) => ({ ...current, planDeviationNote: event.target.value }))} rows={2} value={form.planDeviationNote} />
        </ReviewField>
        <ReviewField label="明天只改 1 件事">
          <textarea className={buildFieldClassName(Boolean(errors.nextDayOneFix))} onChange={(event) => setDraft((current) => ({ ...current, nextDayOneFix: event.target.value }))} rows={2} value={form.nextDayOneFix} />
          <FieldError message={errors.nextDayOneFix} />
        </ReviewField>
      </div>

      <div className="mt-4 rounded-lg border border-toptrader-line bg-toptrader-panel/82 px-3 py-3">
        <button
          className="tt-secondary px-3 py-2 text-xs font-bold"
          onClick={() => setShowExtras((current) => !current)}
          type="button"
        >
          {showExtras ? '收起补充复盘' : '补充复盘（可选）'}
        </button>
        {showExtras ? (
          <div className="mt-3 grid gap-3">
            <ReviewField label="情绪问题">
              <textarea className={buildFieldClassName(Boolean(errors.emotionIssue))} onChange={(event) => setDraft((current) => ({ ...current, emotionIssue: event.target.value }))} rows={2} value={form.emotionIssue} />
              <FieldError message={errors.emotionIssue} />
            </ReviewField>
            <ReviewField label="风控问题">
              <textarea className={buildFieldClassName(Boolean(errors.riskIssue))} onChange={(event) => setDraft((current) => ({ ...current, riskIssue: event.target.value }))} rows={2} value={form.riskIssue} />
              <FieldError message={errors.riskIssue} />
            </ReviewField>
            <ReviewField label="市场问题">
              <textarea className={buildFieldClassName(false)} onChange={(event) => setDraft((current) => ({ ...current, marketIssue: event.target.value }))} rows={2} value={form.marketIssue} />
            </ReviewField>
            <ReviewField label="形态问题">
              <textarea className={buildFieldClassName(false)} onChange={(event) => setDraft((current) => ({ ...current, setupIssue: event.target.value }))} rows={2} value={form.setupIssue} />
            </ReviewField>
            <ReviewField label="最大亏损交易备注">
              <textarea className={buildFieldClassName(false)} onChange={(event) => setDraft((current) => ({ ...current, maxLossTrade: event.target.value }))} rows={2} value={form.maxLossTrade} />
            </ReviewField>
          </div>
        ) : null}
      </div>
      {submitError ? (
        <p className="mt-3 rounded-lg border border-toptrader-rose/30 bg-toptrader-rose/10 px-3 py-2.5 text-xs text-toptrader-rose">
          {submitError}
        </p>
      ) : null}
      {isCurrent ? (
        <div className="mt-4 flex flex-wrap gap-2.5">
          <button className="tt-secondary px-3 py-2 text-xs font-bold disabled:cursor-not-allowed disabled:opacity-60" disabled={hasErrors || isSubmitting} onClick={() => void save()} type="button">
            {isSubmitting ? '保存中…' : '仅保存复盘'}
          </button>
          <button className="tt-primary px-3 py-2 text-xs font-bold disabled:cursor-not-allowed disabled:opacity-60" disabled={hasErrors || isSubmitting} onClick={() => void save({ generateCloseout: true })} type="button">
            {isSubmitting ? '保存中…' : '保存复盘并更新归档'}
          </button>
        </div>
      ) : null}
    </section>
  )
}
