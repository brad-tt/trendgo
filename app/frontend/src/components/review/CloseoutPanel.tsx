import { useMemo, useState } from 'react'

import { MarkdownPreview } from '../MarkdownPreview'
import type { CloseoutPayload } from '../../types'
import { formatTradeDate } from '../../utils/display'
import { MetaBadge, MetaRow } from './reviewUi'

interface CloseoutPanelProps {
  closeout: CloseoutPayload
  isCurrent: boolean
  tradeDate: string
  onGenerated: (updatedCloseout: CloseoutPayload) => Promise<void>
}

function normalizeCloseoutPreviewForDisplay(content: string, tradeDate: string) {
  const tradeDateLabel = formatTradeDate(tradeDate)
  return content
    .replace(/^# TopTrader Day\s+\S+\s+(归档草稿|收口草稿|Closeout Draft)$/m, `# TopTrader ${tradeDateLabel} 归档草稿`)
    .replace(/^- (记录文件|Record file)：? ?`?.*$/gm, `- 归档交易日：${tradeDateLabel}`)
    .replace(/今日/g, '当日')
    .replace(/收口/g, '归档')
}

export function CloseoutPanel({ closeout, isCurrent, tradeDate, onGenerated }: CloseoutPanelProps) {
  const [expanded, setExpanded] = useState(Boolean(closeout.preview))
  const displayPreview = useMemo(
    () => normalizeCloseoutPreviewForDisplay(closeout.preview || '', tradeDate),
    [closeout.preview, tradeDate],
  )

  return (
    <aside className="tt-bento p-4 xl:col-span-3 xl:sticky xl:top-20 xl:self-start">
      <div className="flex flex-wrap items-start justify-between gap-2.5">
        <h2 className="tt-heading-page">归档预览</h2>
        <button className="tt-secondary px-2.5 py-1.5 text-[11px] font-bold" onClick={() => setExpanded((current) => !current)} type="button">
          {expanded ? '收起' : '展开'}
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <MetaBadge label={closeout.exists ? '草稿已生成' : '尚未生成'} tone={closeout.exists ? 'success' : 'neutral'} />
        <MetaBadge label={closeout.stale ? '待重新生成' : '已同步'} tone={closeout.stale ? 'warning' : 'success'} />
        {closeout.legacy ? <MetaBadge label="历史旧版归档文件" tone="warning" /> : null}
      </div>
      <div className="mt-3 rounded-lg border border-toptrader-line bg-toptrader-soft/45 px-3 py-3 text-xs text-toptrader-muted">
        <MetaRow label="归档交易日" value={formatTradeDate(tradeDate)} />
        <MetaRow label="预览状态" value={closeout.preview.trim() ? `已载入 ${closeout.preview.trim().split('\n').length} 行预览` : '尚未载入预览内容'} />
      </div>
      {isCurrent ? (
        <div className="mt-3 flex flex-wrap gap-2.5">
          <button className="tt-secondary px-3 py-2 text-xs font-bold" onClick={() => void onGenerated({ ...closeout, stale: false })} type="button">
            查看草稿
          </button>
          <button className="tt-primary px-3 py-2 text-xs font-bold" onClick={() => void onGenerated({ ...closeout, stale: true })} type="button">
            重新生成
          </button>
        </div>
      ) : null}
      {expanded ? (
        <div className="mt-3 max-h-[520px] overflow-y-auto">
          <MarkdownPreview content={displayPreview} emptyText="生成归档后，这里会直接展示 Markdown 预览。" />
        </div>
      ) : null}
    </aside>
  )
}
