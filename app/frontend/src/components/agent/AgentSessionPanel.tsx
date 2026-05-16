import { useMemo, useState } from 'react'

import type { AgentSessionResponse, DailyRecord } from '../../types'
import { apiClient } from '../../utils/apiClient'
import { displayValue, formatTradeDate } from '../../utils/display'
import type { ToastState } from '../Toast'
import {
  type AgentCommitResponse,
  type PendingAgentPayload,
  buildAutoEventMessage,
  buildCommitPayload,
  buildCommitPayloadFromPending,
  buildPendingPayload,
  buildStopWorkflowMessages,
  prioritizeMissingLabels,
  shouldAutoCommitPending,
} from './agentCommit'

interface AgentSessionPanelProps {
  currentMarket: 'HK' | 'US'
  currentTradeDate: string
  onCommitted: (day: DailyRecord) => void
  onToast: (toast: ToastState) => void
}

export function AgentSessionPanel({
  currentMarket,
  currentTradeDate,
  onCommitted,
  onToast,
}: AgentSessionPanelProps) {
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [response, setResponse] = useState<AgentSessionResponse | null>(null)
  const [commitResponse, setCommitResponse] = useState<AgentCommitResponse | null>(null)
  const [pending, setPending] = useState<PendingAgentPayload | null>(null)

  const canSubmit = note.trim().length >= 6 && !submitting
  const summary = useMemo(() => {
    if (!response) return null
    const workflowResult = response.workflow.result
    const missingLabels = prioritizeMissingLabels(workflowResult.missingFields || [], workflowResult.missingLabels || [])
    return {
      intent: response.intent,
      confidence: `${Math.round((response.intentConfidence || 0) * 100)}%`,
      nextAction: response.nextAction,
      stage: response.context.stage.stageLabel,
      followUps: workflowResult.followUpQuestions || [],
      missingLabels,
      committed: Boolean(commitResponse?.committed),
      canCommit: response.intent !== 'unknown' && Boolean(workflowResult.canWrite),
      isPending: Boolean(pending) && !commitResponse?.committed,
      isBackfill: ['review', 'closeout', 'done'].includes(response.context.today.sessionStatus) && ['open_trade', 'close_trade'].includes(response.intent),
      proposal: workflowResult.proposal || {},
    }
  }, [commitResponse?.committed, pending, response])

  const stopMessages = useMemo(() => buildStopWorkflowMessages(commitResponse?.day, commitResponse || undefined), [commitResponse])
  const autoEventMessage = commitResponse ? buildAutoEventMessage(commitResponse) : ''

  const parse = async () => {
    if (!canSubmit) return
    setSubmitting(true)
    setCommitResponse(null)
    try {
      const result = await apiClient.post<AgentSessionResponse>('/api/agent/session', {
        tradeDate: currentTradeDate,
        market: currentMarket,
        rawNote: note,
        autoCommit: false,
      })
      setResponse(result)
      const nextPending = buildPendingPayload(result.workflow.result, {
        intent: result.intent,
        tradeDate: currentTradeDate,
        market: currentMarket,
        rawNote: note,
        previous: pending,
      })
      const canWrite = result.intent !== 'unknown' && Boolean(result.workflow.result.canWrite)
      if (shouldAutoCommitPending(nextPending, canWrite)) {
        setPending(nextPending)
        await commitPending(nextPending)
      } else if (result.intent !== 'unknown' && !result.workflow.result.committed) {
        setPending(nextPending)
      }
      onToast({
        message: canWrite && !nextPending.explicitConfirmRequired ? '字段已齐，正在写入正式交易。' : result.message,
        tone: 'success',
      })
    } catch (error) {
      onToast({
        message: error instanceof Error ? error.message : 'Agent 解析失败。',
        tone: 'error',
      })
    } finally {
      setSubmitting(false)
    }
  }

  const commitPending = async (payload: PendingAgentPayload) => {
    const result = await apiClient.post<AgentCommitResponse>('/api/agent/commit', buildCommitPayloadFromPending(payload))
    setCommitResponse(result)
    if (result.committed && result.day) {
      onCommitted(result.day)
      setPending(null)
    }
    return result
  }

  const commit = async () => {
    if (!response || !summary?.canCommit || submitting) return
    setSubmitting(true)
    try {
      const payload = buildCommitPayload(response.workflow.result, {
        intent: response.intent,
        tradeDate: currentTradeDate,
        market: currentMarket,
        rawNote: note,
      })
      const result = await apiClient.post<AgentCommitResponse>('/api/agent/commit', payload)
      setCommitResponse(result)
      if (result.committed && result.day) {
        onCommitted(result.day)
        setPending(null)
      }
      onToast({
        message: result.message,
        tone: result.committed ? 'success' : 'error',
      })
    } catch (error) {
      onToast({
        message: error instanceof Error ? error.message : 'Agent 结构化提交失败。',
        tone: 'error',
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="tt-bento-panel accent">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.18em] text-toptrader-brand">Agent Commit</div>
          <h3 className="mt-2 tt-heading-card">一句话口述记录</h3>
          <p className="mt-1 text-xs leading-5 text-toptrader-muted">
            字段不足时会在当前会话里待补；补齐后自动结构化提交。当前目标日期是 {formatTradeDate(currentTradeDate)}，市场是 {displayValue(currentMarket)}。
          </p>
        </div>
        <div className="rounded-lg border border-toptrader-line bg-toptrader-panel px-3 py-2 text-[11px] font-semibold text-toptrader-muted">
          待补不入库
        </div>
      </div>

      <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
        <div className="space-y-3">
          <textarea
            className="tt-input min-h-[160px] resize-y"
            onChange={(event) => setNote(event.target.value)}
            placeholder="例如：10:05 做恒指牛证 546324，入场 0.036，仓位 100000，A级，趋势回踩，止损 0.030，方向位置确认，过滤通过。"
            value={note}
          />
          <div className="flex flex-wrap gap-2">
            <button
              className="rounded-lg border border-toptrader-line bg-toptrader-panel px-3 py-2 text-xs font-bold text-toptrader-ink transition hover:border-toptrader-brand/40 hover:text-toptrader-brand disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!canSubmit}
              onClick={() => void parse()}
              type="button"
            >
              {submitting ? '处理中...' : pending ? '补充字段' : '解析字段'}
            </button>
            <button
              className="rounded-lg bg-toptrader-brand px-3 py-2 text-xs font-black text-toptrader-mist transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!summary?.canCommit || submitting || Boolean(commitResponse?.committed)}
              onClick={() => void commit()}
              type="button"
            >
              {submitting ? '提交中...' : '结构化提交'}
            </button>
          </div>
        </div>

        <div className="rounded-lg border border-toptrader-line bg-toptrader-panel/92 px-3 py-3">
          {summary ? (
            <div className="space-y-3">
              <div className="grid gap-2 sm:grid-cols-2">
                <InfoRow label="识别意图" value={summary.intent} />
                <InfoRow label="置信度" value={summary.confidence} />
                <InfoRow label="当前阶段" value={summary.stage} />
                <InfoRow label="正式写入" value={summary.committed ? '是' : '否'} />
              </div>
              {summary.isPending ? <Notice text="当前有待补字段，只保存在本页面会话中，不是正式交易；补齐后会自动写入。" tone="warning" /> : null}
              {pending?.explicitConfirmRequired ? <Notice text="检测到讨论/不要写/字段冲突，本次不会自动提交；请确认后再点结构化提交。" tone="warning" /> : null}
              <ListBlock items={pending?.conflictMessages || []} title="字段冲突" tone="danger" />
              {summary.isBackfill ? <Notice text="当前处在盘后阶段，这次会按补录盘中交易处理。" tone="warning" /> : null}
              <InfoRow label="下一步动作" value={summary.nextAction} />
              <ListBlock items={summary.missingLabels} title="优先补这些字段" />
              <ListBlock items={summary.followUps.slice(0, 3)} title="下一句建议" />
              <FieldPreview fields={summary.proposal} />
              {commitResponse ? <CommitResult result={commitResponse} /> : null}
              {autoEventMessage ? <Notice text={autoEventMessage} tone="warning" /> : null}
              <ListBlock items={stopMessages} title="停手处理" tone="danger" />
            </div>
          ) : (
            <p className="text-sm leading-6 text-toptrader-muted">
              这里会显示 Agent 提取出的字段、核心缺口和写入结果。字段不足时只在当前会话待补，不会进入数据库。
            </p>
          )}
        </div>
      </div>
    </section>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-toptrader-line bg-toptrader-soft/40 px-3 py-2">
      <div className="text-[11px] font-semibold text-toptrader-muted">{label}</div>
      <div className="mt-1 text-sm font-bold text-toptrader-ink">{value || '--'}</div>
    </div>
  )
}

function Notice({ text, tone = 'neutral' }: { text: string; tone?: 'neutral' | 'warning' }) {
  const toneClass = tone === 'warning' ? 'border-amber-400/40 bg-amber-400/10 text-amber-100' : 'border-toptrader-line bg-toptrader-soft/35 text-toptrader-ink'
  return <div className={`rounded-lg border px-3 py-2 text-xs leading-5 ${toneClass}`}>{text}</div>
}

function ListBlock({ title, items, tone = 'neutral' }: { title: string; items: string[]; tone?: 'neutral' | 'danger' }) {
  if (!items.length) return null
  const itemClass = tone === 'danger' ? 'border-rose-400/40 bg-rose-400/10 text-rose-100' : 'border-toptrader-line bg-toptrader-soft/35 text-toptrader-ink'
  return (
    <div>
      <div className="text-[11px] font-semibold tracking-[0.08em] text-toptrader-muted">{title}</div>
      <div className="mt-2 space-y-2">
        {items.map((item) => (
          <div key={item} className={`rounded-lg border px-3 py-2 text-xs leading-5 ${itemClass}`}>
            {item}
          </div>
        ))}
      </div>
    </div>
  )
}

function FieldPreview({ fields }: { fields: Record<string, unknown> }) {
  const rows = Object.entries(fields)
    .filter(([, value]) => value !== '' && value !== null && value !== undefined)
    .slice(0, 10)
  if (!rows.length) return null
  return (
    <div>
      <div className="text-[11px] font-semibold tracking-[0.08em] text-toptrader-muted">已提取字段</div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {rows.map(([key, value]) => (
          <InfoRow key={key} label={key} value={typeof value === 'boolean' ? (value ? '是' : '否') : displayValue(String(value))} />
        ))}
      </div>
    </div>
  )
}

function CommitResult({ result }: { result: AgentCommitResponse }) {
  const missing = result.missingLabels || result.missingFields || []
  return (
    <div className="rounded-lg border border-toptrader-line bg-toptrader-soft/35 px-3 py-2">
      <div className="text-[11px] font-semibold text-toptrader-muted">写入结果</div>
      <div className="mt-1 text-sm font-bold text-toptrader-ink">{result.committed ? '已正式写入' : '未写入'}</div>
      <div className="mt-1 text-xs leading-5 text-toptrader-muted">{result.message}</div>
      {result.targetTradeId ? <div className="mt-1 text-xs text-toptrader-muted">目标交易：{result.targetTradeId}</div> : null}
      {result.autoEventId ? <div className="mt-1 text-xs text-toptrader-muted">联动纪律事件：{result.autoEventId}</div> : null}
      <ListBlock items={result.feedbackMessages || []} title="系统提示" />
      {missing.length ? <ListBlock items={missing.slice(0, 3)} title="仍缺字段" /> : null}
    </div>
  )
}
