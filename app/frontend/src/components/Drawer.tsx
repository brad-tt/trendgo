import type { ReactNode } from 'react'

interface DrawerProps {
  children: ReactNode
  headerAction?: ReactNode
  isOpen: boolean
  onClose: () => void
  title: string
}

export function Drawer({ children, headerAction, isOpen, onClose, title }: DrawerProps) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-40 grid place-items-center bg-slate-950/42 p-3 backdrop-blur-sm animate-[tt-fade-in_0.2s_ease-out_both]">
      <button
        aria-label="关闭弹窗"
        className="absolute inset-0 cursor-default"
        onClick={onClose}
        type="button"
      />
      <aside
        className="relative flex max-h-[calc(100vh-1.5rem)] w-full max-w-[52rem] flex-col overflow-hidden rounded-lg border border-toptrader-line bg-toptrader-panel shadow-[0_22px_72px_rgba(0,0,0,0.38)] animate-[tt-slide-in-right_0.25s_ease-out_both]"
      >
        <header className="flex items-center justify-between border-b border-toptrader-line bg-toptrader-panel px-4 py-3">
          <h3 className="tt-heading-page">{title}</h3>
          {headerAction ?? (
            <button
              className="tt-secondary px-3 py-1.5 text-xs font-bold"
              onClick={onClose}
              type="button"
            >
              关闭
            </button>
          )}
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">{children}</div>
      </aside>
    </div>
  )
}
