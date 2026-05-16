import { useState } from 'react'

import { Drawer } from '../Drawer'
import type { DailyRecord, DayActionResponse, RuleEvent } from '../../types'
import { apiClient } from '../../utils/apiClient'
import { displayValue } from '../../utils/display'
import { Badge } from '../ui/Badge'
import { TradeField } from './reviewUi'
import { fieldClassName } from './reviewUtils'
import { normalizeClockValue } from './tradeForm'

interface RuleEventPanelProps {
  events: RuleEvent[]
  tradeDate: string
  market: string
  isCurrent: boolean
  tradeIds?: string[]
  onEventsChange: (updatedDay: DailyRecord) => void
}

type EventFormState = {
  actionTaken: string
  eventTime: string
  eventType: string
  followUpNote: string
  linkedTradeId: string
  severity: string
  triggerReason: string
}

const eventPresets = [
  { key: 'open_whipsaw_pause', label: '开盘乱甩暂停' },
  { key: 'stop_reverse_pause', label: '止损后反手冲动' },
  { key: 'profit_protect', label: '盈利回吐保护' },
  { key: 'low_quality_stop', label: '低质量诱惑停手' },
  { key: 'manual_stop_day', label: '当日停手' },
] as const

const eventPresetGroups = [
  {
    title: '暂停复核',
    keys: ['open_whipsaw_pause', 'stop_reverse_pause', 'profit_protect'] as const,
  },
  {
    title: '停止执行',
    keys: ['low_quality_stop', 'manual_stop_day'] as const,
  },
] as const

function currentClockValue() {
  const now = new Date()
  return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`
}

function defaultEventForm(): EventFormState {
  return {
    actionTaken: '',
    eventTime: currentClockValue(),
    eventType: 'emotion_trigger',
    followUpNote: '',
    linkedTradeId: '',
    severity: 'warning',
    triggerReason: '',
  }
}

export function RuleEventPanel({
  events,
  tradeDate,
  market,
  isCurrent,
  tradeIds = [],
  onEventsChange,
}: RuleEventPanelProps) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editingEventId, setEditingEventId] = useState<string | null>(null)
  const [form, setForm] = useState<EventFormState>(defaultEventForm)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const openCreate = () => {
    setEditingEventId(null)
    setForm(defaultEventForm())
    setDrawerOpen(true)
  }

  const openEdit = (event: RuleEvent) => {
    setEditingEventId(event.eventId)
    setForm({
      actionTaken: event.actionTaken,
      eventTime: normalizeClockValue(event.time) ?? '',
      eventType: event.eventType,
      followUpNote: event.followUpNote,
      linkedTradeId: event.linkedTradeId,
      severity: event.severity,
      triggerReason: event.triggerReason,
    })
    setDrawerOpen(true)
  }

  const closeDrawer = () => {
    setDrawerOpen(false)
    setEditingEventId(null)
  }

  const save = async () => {
    setIsSubmitting(true)
    try {
      const payload = {
        market,
        tradeDate,
        actionTaken: form.actionTaken,
        eventTime: form.eventTime,
        eventType: form.eventType,
        followUpNote: form.followUpNote,
        linkedTradeId: form.linkedTradeId,
        severity: form.severity,
        triggerReason: form.triggerReason,
      }
      const response = editingEventId
        ? await apiClient.put<DayActionResponse>(
            `/api/day-records/rule-events/${editingEventId}?tradeDate=${encodeURIComponent(tradeDate)}&market=${encodeURIComponent(market)}`,
            payload,
          )
        : await apiClient.post<DayActionResponse>('/api/day-records/rule-events', payload)
      onEventsChange(response.day)
      closeDrawer()
    } finally {
      setIsSubmitting(false)
    }
  }

  const remove = async (eventId: string) => {
    const response = await apiClient.delete<DayActionResponse>(
      `/api/day-records/rule-events/${eventId}?tradeDate=${encodeURIComponent(tradeDate)}&market=${encodeURIComponent(market)}`,
    )
    onEventsChange(response.day)
  }

  const createPreset = async (presetKey: string) => {
    const response = await apiClient.post<DayActionResponse>('/api/day-records/rule-events/presets', {
      market,
      presetKey,
      tradeDate,
    })
    onEventsChange(response.day)
  }

  const criticalCount = events.filter((event) => event.severity === 'critical').length
  const stopLikeCount = events.filter((event) => event.severity === 'stop' || event.eventType === 'forced_pause' || event.eventType === 'forced_stop').length

  return (
    <>
      <section className="tt-bento p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2.5">
          <div>
            <h2 className="tt-heading-page">纪律控制区</h2>
          </div>
          {isCurrent ? (
            <button className="tt-secondary px-3 py-2 text-xs font-bold" onClick={openCreate} type="button">
              新增事件
            </button>
          ) : null}
        </div>
        <div className="mb-3 grid gap-3 sm:grid-cols-3">
          <ControlMetric label="事件总数" value={String(events.length)} />
          <ControlMetric label="暂停 / 停手" value={String(stopLikeCount)} />
          <ControlMetric label="严重事件" value={String(criticalCount)} />
        </div>
        {!isCurrent ? null : (
          <div className="mb-3 rounded-xl border border-toptrader-line bg-toptrader-panel/92 px-3 py-3 text-[11px] leading-5 text-toptrader-muted">
            空仓日也允许补纪律事件，用来记录等待失守、差点冲动开仓、暂停或停手动作。
          </div>
        )}
        {isCurrent ? (
          <div className="mb-3 rounded-xl border border-toptrader-line bg-toptrader-panel/92 px-3 py-3">
            <div className="text-[11px] font-semibold tracking-[0.08em] text-toptrader-muted">快捷控制动作</div>
            <div className="mt-3 space-y-3">
              {eventPresetGroups.map((group) => (
                <div key={group.title}>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-toptrader-muted">{group.title}</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {group.keys.map((key) => {
                      const preset = eventPresets.find((item) => item.key === key)
                      if (!preset) return null
                      return (
                        <button key={preset.key} className="tt-secondary px-3 py-2 text-[11px] font-bold" onClick={() => void createPreset(preset.key)} type="button">
                          {preset.label}
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
        <div className="space-y-3">
          {events.map((event) => (
            <div key={event.eventId} className="rounded-xl border border-toptrader-line bg-toptrader-panel px-3 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="font-semibold text-toptrader-accent">{event.eventId}</div>
                    <Badge label={displayValue(event.eventType)} tone={event.eventType === 'forced_stop' ? 'danger' : event.eventType === 'forced_pause' ? 'warning' : 'neutral'} />
                    <Badge label={displayValue(event.severity)} tone={event.severity === 'critical' ? 'danger' : event.severity === 'stop' ? 'warning' : 'neutral'} />
                  </div>
                  <div className="mt-1 text-xs text-toptrader-muted">{event.time || '--'}{event.linkedTradeId ? ` / 关联 ${event.linkedTradeId}` : ''}</div>
                </div>
                {isCurrent ? (
                  <div className="flex gap-1.5">
                    <button className="tt-secondary px-2.5 py-1.5 text-[11px] font-bold" onClick={() => openEdit(event)} type="button">
                      编辑
                    </button>
                    <button className="rounded-md border border-toptrader-rose/30 bg-toptrader-panel px-2.5 py-1.5 text-[11px] font-bold text-toptrader-rose transition hover:bg-toptrader-rose/5" onClick={() => void remove(event.eventId)} type="button">
                      删除
                    </button>
                  </div>
                ) : (
                  <span className="text-xs text-toptrader-muted">历史只读</span>
                )}
              </div>

              <div className="mt-3 grid gap-2">
                <EventFact label="触发原因" value={event.triggerReason || '--'} />
                <EventFact label="采取动作" value={event.actionTaken || '--'} />
                {event.followUpNote ? <EventFact label="后续说明" value={event.followUpNote} /> : null}
              </div>
            </div>
          ))}
          {!events.length ? (
            <div className="rounded-xl border border-dashed border-toptrader-line bg-toptrader-panel/70 px-4 py-6 text-center text-xs text-toptrader-muted">
              当前没有纪律事件。
            </div>
          ) : null}
        </div>
      </section>

      <Drawer
        headerAction={
          <div className="flex items-center gap-2">
            <button className="tt-secondary px-3 py-1.5 text-xs font-bold" onClick={closeDrawer} type="button">
              取消
            </button>
            <button
              className="tt-primary px-3 py-1.5 text-xs font-bold disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isSubmitting}
              onClick={() => void save()}
              type="button"
            >
              {isSubmitting ? '保存中…' : editingEventId ? '保存更新' : '保存纪律事件'}
            </button>
          </div>
        }
        isOpen={drawerOpen}
        onClose={closeDrawer}
        title={editingEventId ? `编辑 ${editingEventId}` : '记录纪律事件'}
      >
        <div className="grid gap-3 md:grid-cols-2">
          <TradeField label="时间">
            <input
              className={fieldClassName}
              onBlur={(event) => {
                const normalized = normalizeClockValue(event.target.value)
                if (normalized === null) return
                setForm((current) => ({ ...current, eventTime: normalized }))
              }}
              onChange={(event) => setForm((current) => ({ ...current, eventTime: event.target.value }))}
              step="60"
              type="time"
              value={form.eventTime}
            />
          </TradeField>
          <TradeField label="类型">
            <select className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, eventType: event.target.value }))} value={form.eventType}>
              <option value="rule_violation">规则违规</option>
              <option value="emotion_trigger">情绪触发</option>
              <option value="forced_pause">强制暂停</option>
              <option value="forced_stop">强制停手</option>
              <option value="overtrade_signal">过度交易信号</option>
            </select>
          </TradeField>
          <TradeField label="严重级别">
            <select className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, severity: event.target.value }))} value={form.severity}>
              <option value="warning">预警</option>
              <option value="stop">暂停</option>
              <option value="critical">严重</option>
            </select>
          </TradeField>
          <TradeField label="关联交易">
            <select className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, linkedTradeId: event.target.value }))} value={form.linkedTradeId}>
              <option value="">不关联交易</option>
              {tradeIds.map((tradeId) => (
                <option key={tradeId} value={tradeId}>
                  {tradeId}
                </option>
              ))}
            </select>
          </TradeField>
          <TradeField className="md:col-span-2" label="触发原因">
            <textarea className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, triggerReason: event.target.value }))} rows={3} value={form.triggerReason} />
          </TradeField>
          <TradeField className="md:col-span-2" label="采取动作">
            <textarea className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, actionTaken: event.target.value }))} rows={3} value={form.actionTaken} />
          </TradeField>
          <TradeField className="md:col-span-2" label="后续说明">
            <textarea className={fieldClassName} onChange={(event) => setForm((current) => ({ ...current, followUpNote: event.target.value }))} rows={3} value={form.followUpNote} />
          </TradeField>
        </div>
        <div className="mt-4 flex justify-end gap-2.5">
          <button className="tt-secondary px-3 py-2 text-xs font-bold" onClick={closeDrawer} type="button">
            取消
          </button>
          <button className="tt-primary px-3 py-2 text-xs font-bold disabled:cursor-not-allowed disabled:opacity-60" disabled={isSubmitting} onClick={() => void save()} type="button">
            {isSubmitting ? '保存中…' : '保存纪律事件'}
          </button>
        </div>
      </Drawer>
    </>
  )
}

function ControlMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-toptrader-line bg-toptrader-panel/92 px-3 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-toptrader-muted">{label}</div>
      <div className="mt-1 text-base font-bold text-toptrader-accent">{value}</div>
    </div>
  )
}

function EventFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-toptrader-line bg-toptrader-soft/35 px-3 py-2.5">
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-toptrader-muted">{label}</div>
      <div className="mt-1 text-[12px] leading-5 text-toptrader-accent">{value}</div>
    </div>
  )
}
