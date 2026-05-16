export function StaticRuleCard({
  accentClassName,
  compact = false,
  helper,
  items,
  title,
}: {
  accentClassName: string
  compact?: boolean
  helper: string
  items: string[]
  title: string
}) {
  return (
    <div className={`rounded-[18px] border border-toptrader-line bg-gradient-to-br ${accentClassName} ${compact ? 'p-3' : 'p-4'} shadow-[0_10px_24px_rgba(24,32,47,0.08)]`}>
      <h4 className={compact ? 'text-[15px] font-semibold tracking-tight text-toptrader-accent' : 'tt-heading-page text-lg'}>{title}</h4>
      <p className={compact ? 'mt-1 text-[11px] leading-4 text-toptrader-muted' : 'mt-1.5 text-xs leading-5 text-toptrader-muted'}>{helper}</p>
      <div className={compact ? 'mt-2 space-y-2' : 'mt-3 space-y-2.5'}>
        {items.map((item, index) => (
          <div key={item} className={`rounded-xl border border-toptrader-line bg-toptrader-panel/88 ${compact ? 'px-2.5 py-2' : 'px-3 py-2.5'} shadow-sm`}>
            <div className={compact ? 'flex items-start gap-2' : 'flex items-start gap-2.5'}>
              <span className={`${compact ? 'mt-0 grid h-5 w-5 text-[9px]' : 'mt-0.5 grid h-6 w-6 text-[10px]'} shrink-0 place-items-center rounded-full bg-toptrader-brand font-black text-toptrader-mist`}>
                {index + 1}
              </span>
              <p className={compact ? 'text-[11px] leading-5 text-toptrader-accent' : 'text-[12px] leading-5 text-toptrader-accent'}>{item}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
