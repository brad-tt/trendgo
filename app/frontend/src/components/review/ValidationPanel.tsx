import { useMemo, useState } from 'react'

import type { DailyRecord, DayActionResponse, ValidationFields } from '../../types'
import { apiClient } from '../../utils/apiClient'
import { FieldError, ReviewField, ToggleRow } from './reviewUi'
import { buildFieldClassName } from './reviewUtils'

interface ValidationPanelProps {
  tradingToday?: boolean
  validation: ValidationFields
  tradeDate: string
  market: string
  isCurrent: boolean
  onSave: (updatedDay: DailyRecord) => void | Promise<void>
  onSaveAndGenerateCloseout?: (updatedDay: DailyRecord) => void | Promise<void>
}

type ValidationFormState = {
  emotionalOvertradeDetected: boolean
  impulsiveTradeDetected: boolean
  intradayRecordComplete: boolean
  noStopLossTradeDetected: boolean
  noTradeDay: boolean
  noTradeNote: string
  postMarketReviewDone: boolean
  preMarketDone: boolean
}

function isBlank(value: string) {
  return value.trim() === ''
}

function getValidationErrors(form: ValidationFormState) {
  const errors: Partial<Record<keyof ValidationFormState, string>> = {}
  if (form.noTradeDay && isBlank(form.noTradeNote)) {
    errors.noTradeNote = '空仓日需要补充说明，避免记录失真。'
  }
  return errors
}

export function ValidationPanel({ validation, tradeDate, market, isCurrent, onSave, onSaveAndGenerateCloseout, tradingToday = true }: ValidationPanelProps) {
  const [draft, setDraft] = useState<ValidationFormState>({
    emotionalOvertradeDetected: validation.emotionalOvertradeDetected,
    impulsiveTradeDetected: validation.impulsiveTradeDetected,
    intradayRecordComplete: validation.intradayRecordComplete,
    noStopLossTradeDetected: validation.noStopLossTradeDetected,
    noTradeDay: validation.noTradeDay,
    noTradeNote: validation.noTradeNote,
    postMarketReviewDone: validation.postMarketReviewDone,
    preMarketDone: validation.preMarketDone,
  })
  const form = useMemo(
    () => ({
      ...validation,
      ...draft,
      noTradeDay: tradingToday ? draft.noTradeDay : true,
    }),
    [draft, tradingToday, validation],
  )
  const errors = useMemo(() => getValidationErrors(form), [form])
  const hasErrors = Object.keys(errors).length > 0
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')

  const save = async (options?: { generateCloseout?: boolean }) => {
    setIsSubmitting(true)
    setSubmitError('')
    try {
      const response = await apiClient.put<DayActionResponse>('/api/day-records/validation', {
        emotionalOvertradeDetected: form.emotionalOvertradeDetected,
        impulsiveTradeDetected: form.impulsiveTradeDetected,
        intradayRecordComplete: form.intradayRecordComplete,
        mainImprovementOfDay: validation.mainImprovementOfDay,
        mainIssueOfDay: validation.mainIssueOfDay,
        market,
        noStopLossTradeDetected: form.noStopLossTradeDetected,
        noTradeDay: form.noTradeDay,
        noTradeNote: form.noTradeNote,
        postMarketReviewDone: form.postMarketReviewDone,
        preMarketDone: form.preMarketDone,
        tradeDate,
      })
      if (options?.generateCloseout && onSaveAndGenerateCloseout) {
        await onSaveAndGenerateCloseout(response.day)
      } else {
        await onSave(response.day)
      }
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : '保存验证失败，请重试。')
    } finally {
      setIsSubmitting(false)
    }
  }

  const closeNoTradeDay = async () => {
    setIsSubmitting(true)
    setSubmitError('')
    try {
      const response = await apiClient.post<DayActionResponse>('/api/day-records/close-no-trade', {
        market,
        tradeDate,
      })
      await onSave(response.day)
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : '空仓归档失败，请重试。')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="tt-bento p-4">
      <h2 className="tt-heading-page">验证与归档</h2>
      {hasErrors ? (
        <p className="mt-3 rounded-lg border border-toptrader-rose/30 bg-toptrader-rose/10 px-3 py-2.5 text-xs text-toptrader-rose">
          验证表单里还有 {Object.keys(errors).length} 个待补项。
        </p>
      ) : null}
      <div className="mt-3 grid gap-2.5 text-sm text-toptrader-muted">
        <ToggleRow checked={form.preMarketDone} label="盘前完成" onChange={(checked) => setDraft((current) => ({ ...current, preMarketDone: checked }))} />
        <ToggleRow checked={form.intradayRecordComplete} label="盘中记录完成" onChange={(checked) => setDraft((current) => ({ ...current, intradayRecordComplete: checked }))} />
        <ToggleRow checked={form.postMarketReviewDone} label="盘后复盘完成" onChange={(checked) => setDraft((current) => ({ ...current, postMarketReviewDone: checked }))} />
        <ToggleRow checked={form.impulsiveTradeDetected} label="出现冲动交易" onChange={(checked) => setDraft((current) => ({ ...current, impulsiveTradeDetected: checked }))} />
        <ToggleRow checked={form.noStopLossTradeDetected} label="出现无止损 / 止损失守" onChange={(checked) => setDraft((current) => ({ ...current, noStopLossTradeDetected: checked }))} />
        <ToggleRow checked={form.emotionalOvertradeDetected} label="出现情绪化过度交易" onChange={(checked) => setDraft((current) => ({ ...current, emotionalOvertradeDetected: checked }))} />
        <ToggleRow checked={form.noTradeDay} label={tradingToday ? '空仓日' : '今天已设为不交易，按空仓日流程处理'} onChange={(checked) => setDraft((current) => ({ ...current, noTradeDay: checked }))} />
        {!tradingToday ? (
          <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-xs leading-5 text-amber-400">
            因为盘前已明确设置“今天不交易”，这里默认按空仓日标准要求空仓说明，不再按普通交易日要求“当日主要问题”。
          </p>
        ) : null}
        {form.noTradeDay ? (
          <ReviewField label="空仓说明">
            <textarea className={buildFieldClassName(Boolean(errors.noTradeNote))} onChange={(event) => setDraft((current) => ({ ...current, noTradeNote: event.target.value }))} rows={2} value={form.noTradeNote} />
            <FieldError message={errors.noTradeNote} />
          </ReviewField>
        ) : null}
      </div>
      {submitError ? (
        <p className="mt-3 rounded-lg border border-toptrader-rose/30 bg-toptrader-rose/10 px-3 py-2.5 text-xs text-toptrader-rose">
          {submitError}
        </p>
      ) : null}
      {isCurrent ? (
        <div className="mt-3 flex flex-wrap gap-2.5">
          <button className="tt-secondary px-3 py-2 text-xs font-bold disabled:cursor-not-allowed disabled:opacity-60" disabled={isSubmitting} onClick={() => void closeNoTradeDay()} type="button">
            空仓归档
          </button>
          <button className="tt-secondary px-3 py-2 text-xs font-bold disabled:cursor-not-allowed disabled:opacity-60" disabled={hasErrors || isSubmitting} onClick={() => void save()} type="button">
            {isSubmitting ? '保存中…' : '仅保存验证'}
          </button>
          <button className="tt-primary px-3 py-2 text-xs font-bold disabled:cursor-not-allowed disabled:opacity-60" disabled={hasErrors || isSubmitting} onClick={() => void save({ generateCloseout: true })} type="button">
            {isSubmitting ? '保存中…' : '保存验证并更新归档'}
          </button>
        </div>
      ) : null}
    </section>
  )
}
