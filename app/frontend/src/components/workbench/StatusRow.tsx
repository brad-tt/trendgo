export function StatusRow({
  label,
  tone = 'neutral',
  value,
}: {
  label: string
  tone?: 'good' | 'neutral' | 'warn'
  value: string
}) {
  const toneClass =
    tone === 'good'
      ? 'bg-toptrader-brand/10 text-toptrader-brand'
      : tone === 'warn'
        ? 'bg-amber-500/10 text-amber-400'
        : 'bg-toptrader-soft text-toptrader-muted'

  return (
    <div className={['rounded-lg border border-toptrader-line px-3 py-2 text-[11px]', toneClass].join(' ')}>
      <div className="text-[9px] font-semibold uppercase tracking-[0.12em] opacity-75">{label}</div>
      <div className="mt-0.5 font-bold">{value}</div>
    </div>
  )
}
