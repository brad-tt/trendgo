import type { ReactNode } from 'react'

export function MarkdownPreview({
  content,
  emptyText = '暂无可预览内容。',
}: {
  content: string
  emptyText?: string
}) {
  const text = content.trim()
  if (!text) {
    return (
      <div className="rounded-2xl border border-dashed border-toptrader-line bg-toptrader-soft/30 px-4 py-6 text-sm text-toptrader-muted">
        {emptyText}
      </div>
    )
  }

  const lines = text.split('\n')
  const blocks: ReactNode[] = []
  let listItems: string[] = []

  const flushList = () => {
    if (!listItems.length) return
    blocks.push(
      <ul
        key={`list-${blocks.length}`}
        className="ml-5 list-disc space-y-2 text-sm leading-6 text-toptrader-ink"
      >
        {listItems.map((item, index) => (
          <li key={`${item}-${index}`}>{item}</li>
        ))}
      </ul>,
    )
    listItems = []
  }

  lines.forEach((rawLine) => {
    const line = rawLine.trim()
    if (!line) {
      flushList()
      return
    }
    if (line.startsWith('- ')) {
      listItems.push(line.slice(2))
      return
    }
    flushList()
    if (line.startsWith('### ')) {
      blocks.push(
        <h4
          key={`${line}-${blocks.length}`}
          className="text-base font-semibold tracking-tight text-toptrader-accent"
        >
          {line.slice(4)}
        </h4>,
      )
      return
    }
    if (line.startsWith('## ')) {
      blocks.push(
        <h3
          key={`${line}-${blocks.length}`}
          className="text-lg font-semibold tracking-tight text-toptrader-accent"
        >
          {line.slice(3)}
        </h3>,
      )
      return
    }
    if (line.startsWith('# ')) {
      blocks.push(
        <h2
          key={`${line}-${blocks.length}`}
          className="text-xl font-semibold tracking-tight text-toptrader-accent"
        >
          {line.slice(2)}
        </h2>,
      )
      return
    }
    blocks.push(
      <p key={`${line}-${blocks.length}`} className="text-sm leading-6 text-toptrader-ink">
        {line}
      </p>,
    )
  })

  flushList()

  return (
    <div className="space-y-4 rounded-2xl border border-toptrader-line bg-toptrader-panel px-5 py-5 shadow-[0_14px_40px_rgba(0,0,0,0.2)]">
      {blocks}
    </div>
  )
}
