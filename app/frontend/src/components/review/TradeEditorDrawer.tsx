import { useMemo, useState } from 'react'

import { Drawer } from '../Drawer'
import type { Trade } from '../../types'
import { FieldError, ReadonlyTradeValue, TradeField } from './reviewUi'
import { buildFieldClassName, fieldClassName } from './reviewUtils'
import {
  computeTradeOutcome,
  createTradeForm,
  getTradeErrors,
  normalizeClockValue,
  parseOptionalNumber,
  type TradeEditorMode,
  type TradeFormState,
  type TradeWritePayload,
} from './tradeForm'

interface TradeEditorDrawerProps {
  isOpen: boolean
  mode?: TradeEditorMode
  title: string
  tradingMode: string
  trade?: Trade
  onClose: () => void
  onSubmit: (payload: TradeWritePayload) => Promise<void>
}

export function TradeEditorDrawer({
  isOpen,
  mode = 'edit',
  title,
  tradingMode,
  trade,
  onClose,
  onSubmit,
}: TradeEditorDrawerProps) {
  const initialForm = useMemo(() => createTradeForm(tradingMode, trade), [tradingMode, trade])
  const [form, setForm] = useState<TradeFormState>(initialForm)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')

  const activeForm = form
  const isEditing = mode !== 'create' && Boolean(trade)
  const isCloseMode = mode === 'close'
  const isCreateMode = mode === 'create'

  const sideOptions = tradingMode === 'us_stock_options' ? ['call', 'put'] : ['bull', 'bear']
  const errors = useMemo(() => getTradeErrors(activeForm, mode), [activeForm, mode])
  const outcome = useMemo(() => computeTradeOutcome(activeForm), [activeForm])
  const normalizedTradeTime = normalizeClockValue(activeForm.tradeTime) || ''
  const normalizedExitTime = normalizeClockValue(activeForm.exitTime) || ''
  const hasErrors = Object.keys(errors).length > 0

  const save = async () => {
    if (hasErrors) return
    setIsSubmitting(true)
    setSubmitError('')
    try {
      await onSubmit({
        abcGrade: activeForm.abcGrade,
        abnormalScenario: activeForm.abnormalScenario,
        autoRuleEvent: false,
        certificateFilterPassed: activeForm.certificateFilterPassed,
        certificateSide: activeForm.certificateSide,
        confirmationOk: activeForm.confirmationOk,
        direction: activeForm.direction,
        directionClear: activeForm.directionClear,
        entryPrice: Number(activeForm.entryPrice),
        entryReason: activeForm.entryReason,
        exitPrice: isEditing ? parseOptionalNumber(activeForm.exitPrice) ?? undefined : undefined,
        exitTime: isEditing ? normalizedExitTime || undefined : undefined,
        followedPlan: activeForm.followedPlan,
        instrumentCode: activeForm.instrumentCode,
        instrumentType: activeForm.instrumentType,
        locationOk: activeForm.locationOk,
        pnlAmount: isEditing ? outcome.pnlAmount ?? undefined : undefined,
        positionSize: activeForm.positionSize,
        postTradeEmotion: 'unset',
        result: isEditing ? outcome.result ?? undefined : undefined,
        riskClear: activeForm.riskClear,
        ruleViolation: activeForm.ruleViolation,
        sessionWindow: activeForm.sessionWindow,
        setupType: activeForm.setupType,
        stopLoss: Number(activeForm.stopLoss),
        targetPrice: parseOptionalNumber(activeForm.targetPrice) ?? undefined,
        tradeTime: normalizedTradeTime,
        underlying: activeForm.underlying,
      })
      onClose()
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : '保存失败，请重试。')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Drawer
      headerAction={
        <div className="flex items-center gap-2">
          <button className="tt-secondary px-3 py-1.5 text-xs font-bold" onClick={onClose} type="button">
            取消
          </button>
          <button
            className="tt-primary px-3 py-1.5 text-xs font-bold disabled:cursor-not-allowed disabled:opacity-60"
            disabled={hasErrors || isSubmitting}
            onClick={() => void save()}
            type="button"
          >
            {isSubmitting ? '保存中…' : isCloseMode ? '保存平仓' : isCreateMode ? '保存开仓' : '保存更新'}
          </button>
        </div>
      }
      isOpen={isOpen}
      onClose={onClose}
      title={title}
    >
      <div className="grid gap-4 md:grid-cols-2">
        {!isCloseMode ? (
          <TradeField label="开仓时间">
            <input className={buildFieldClassName(Boolean(errors.tradeTime))} onBlur={(event) => {
              const normalized = normalizeClockValue(event.target.value)
              if (normalized === null) return
              setForm((current) => ({ ...current, tradeTime: normalized }))
            }} onChange={(event) => setForm((current) => ({ ...current, tradeTime: event.target.value }))} step="60" type="time" value={activeForm.tradeTime} />
            <FieldError message={errors.tradeTime} />
          </TradeField>
        ) : (
          <TradeField label="开仓信息">
            <ReadonlyTradeValue helper={`${activeForm.instrumentCode || '--'} / 入场 ${activeForm.entryPrice || '--'} / 仓位 ${activeForm.positionSize || '--'}`} value={activeForm.tradeTime || '未填开仓时间'} />
          </TradeField>
        )}
        {isEditing ? (
          <TradeField label="平仓时间">
            <input className={buildFieldClassName(Boolean(errors.exitTime))} onBlur={(event) => {
              const normalized = normalizeClockValue(event.target.value)
              if (normalized === null) return
              setForm((current) => ({ ...current, exitTime: normalized }))
            }} onChange={(event) => setForm((current) => ({ ...current, exitTime: event.target.value }))} step="60" type="time" value={activeForm.exitTime} />
            <FieldError message={errors.exitTime} />
          </TradeField>
        ) : (
          <TradeField label="记录说明">
            <ReadonlyTradeValue helper="新建时只记录开仓；平仓后再回来编辑这一笔，补平仓时间和价格。" value="先记开仓" />
          </TradeField>
        )}
        {!isCloseMode ? (
        <TradeField label="机会等级">
          <select className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, abcGrade: event.target.value }))} value={activeForm.abcGrade}>
            <option value="">请选择</option>
            <option value="A">A</option>
            <option value="B">B</option>
            <option value="C">C</option>
          </select>
          <FieldError message={errors.abcGrade} />
        </TradeField>
        ) : null}
        {!isCloseMode ? (
        <TradeField label="交易方向">
          <select className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, direction: event.target.value }))} value={activeForm.direction}>
            <option value="long">做多</option>
            <option value="short">做空</option>
          </select>
        </TradeField>
        ) : null}
        {!isCloseMode ? (
        <TradeField label={tradingMode === 'us_stock_options' ? 'Call / Put' : '牛 / 熊证'}>
          <select className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, certificateSide: event.target.value }))} value={activeForm.certificateSide}>
            {sideOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </TradeField>
        ) : null}
        {!isCloseMode ? (
        <TradeField className="md:col-span-2" label="标的代码">
          <input className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, instrumentCode: event.target.value }))} value={activeForm.instrumentCode} />
          <FieldError message={errors.instrumentCode} />
        </TradeField>
        ) : null}
        {!isCloseMode ? (
        <TradeField label="形态">
          <select className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, setupType: event.target.value }))} value={activeForm.setupType}>
            <option value="opening_breakout">开盘突破</option>
            <option value="pullback_reclaim">回踩确认</option>
            <option value="orb_continuation">开盘区间突破延续</option>
            <option value="vwap_reclaim">VWAP 收复</option>
            <option value="trend_pullback">趋势回踩</option>
          </select>
        </TradeField>
        ) : null}
        {!isCloseMode ? (
        <TradeField label="入场价">
          <input className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, entryPrice: event.target.value }))} type="number" value={activeForm.entryPrice} />
          <FieldError message={errors.entryPrice} />
        </TradeField>
        ) : null}
        {!isCloseMode ? (
        <TradeField label="止损">
          <input className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, stopLoss: event.target.value }))} type="number" value={activeForm.stopLoss} />
          <FieldError message={errors.stopLoss} />
        </TradeField>
        ) : null}
        {!isCloseMode ? (
        <TradeField label="止盈价">
          <input className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, targetPrice: event.target.value }))} type="number" value={activeForm.targetPrice} />
        </TradeField>
        ) : null}
        {isEditing ? (
          <TradeField label="平仓价格">
            <input className={buildFieldClassName(Boolean(errors.exitPrice))} onChange={(event) => setForm((current) => ({ ...current, exitPrice: event.target.value }))} type="number" value={activeForm.exitPrice} />
            <FieldError message={errors.exitPrice} />
          </TradeField>
        ) : null}
        {!isCloseMode ? (
        <TradeField label="仓位">
          <input className={buildFieldClassName(Boolean(errors.positionSize))} onChange={(event) => setForm((current) => ({ ...current, positionSize: event.target.value }))} value={activeForm.positionSize} />
          <FieldError message={errors.positionSize} />
        </TradeField>
        ) : null}
        {isCloseMode ? (
          <TradeField label="仓位">
            <ReadonlyTradeValue helper="自动按已有仓位计算盈亏" value={activeForm.positionSize || '--'} />
          </TradeField>
        ) : null}
        {isEditing ? (
          <TradeField label={tradingMode === 'us_stock_options' ? '自动盈亏(USD)' : '自动盈亏(HKD)'}>
            <ReadonlyTradeValue helper={outcome.signedMove === null ? '补完平仓价后自动计算' : outcome.pnlAmount === null ? '仓位需为数字，才能自动算金额' : '已按方向与仓位自动换算'} value={outcome.pnlAmount ?? '待计算'} />
          </TradeField>
        ) : null}
        {!isCloseMode ? (
        <TradeField label="工具过滤">
          <select className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, certificateFilterPassed: event.target.value === 'true' }))} value={activeForm.certificateFilterPassed ? 'true' : 'false'}>
            <option value="true">通过</option>
            <option value="false">未过</option>
          </select>
        </TradeField>
        ) : null}
        {!isCloseMode ? (
        <TradeField label="方向明确">
          <select className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, directionClear: event.target.value === 'true' }))} value={activeForm.directionClear ? 'true' : 'false'}>
            <option value="true">是</option>
            <option value="false">否</option>
          </select>
        </TradeField>
        ) : null}
        {!isCloseMode ? (
        <TradeField label="位置合理">
          <select className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, locationOk: event.target.value === 'true' }))} value={activeForm.locationOk ? 'true' : 'false'}>
            <option value="true">是</option>
            <option value="false">否</option>
          </select>
        </TradeField>
        ) : null}
        {!isCloseMode ? (
        <TradeField label="确认出现">
          <select className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, confirmationOk: event.target.value === 'true' }))} value={activeForm.confirmationOk ? 'true' : 'false'}>
            <option value="true">是</option>
            <option value="false">否</option>
          </select>
        </TradeField>
        ) : null}
        {!isCloseMode ? (
        <TradeField label="风险清楚">
          <select className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, riskClear: event.target.value === 'true' }))} value={activeForm.riskClear ? 'true' : 'false'}>
            <option value="true">是</option>
            <option value="false">否</option>
          </select>
        </TradeField>
        ) : null}
        {!isCloseMode ? (
        <TradeField className="md:col-span-2" label="入场逻辑">
          <textarea className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, entryReason: event.target.value }))} rows={4} value={activeForm.entryReason} />
          <FieldError message={errors.entryReason} />
        </TradeField>
        ) : null}
      </div>

      {submitError ? (
        <div className="mt-4 rounded-2xl border border-toptrader-rose/30 bg-toptrader-rose/10 px-4 py-3 text-sm text-toptrader-rose">
          {submitError}
        </div>
      ) : null}

      <div className="mt-6 flex justify-end gap-3">
        <button className="tt-secondary px-4 py-3 text-sm font-bold" onClick={onClose} type="button">
          取消
        </button>
        <button className="tt-primary px-4 py-3 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-60" disabled={hasErrors || isSubmitting} onClick={() => void save()} type="button">
          {isSubmitting ? '保存中…' : isCloseMode ? '保存平仓' : isCreateMode ? '保存开仓' : '保存交易'}
        </button>
      </div>
    </Drawer>
  )
}
