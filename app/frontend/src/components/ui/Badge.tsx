export function Badge({
  label,
  tone = 'neutral',
}: {
  label: string
  tone?: 'success' | 'warning' | 'danger' | 'neutral'
}) {
  const toneClass =
    tone === 'success'
      ? 'bg-toptrader-brand/15 text-toptrader-brand'
      : tone === 'warning'
        ? 'bg-amber-500/15 text-amber-400'
        : tone === 'danger'
          ? 'bg-toptrader-rose/15 text-toptrader-rose'
          : 'bg-toptrader-soft text-toptrader-ink'

  return <span className={['rounded-full px-2 py-0.5 text-[11px] font-medium', toneClass].join(' ')}>{label}</span>
}
