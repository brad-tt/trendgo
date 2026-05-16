export function SummaryCard({
  helper,
  label,
  value,
}: {
  helper?: string
  label: string
  value: string | number
}) {
  return (
    <div className="rounded-lg border border-toptrader-line bg-gradient-to-br from-toptrader-panel to-toptrader-brand/5 px-3 py-2.5 shadow-sm">
      <p className="text-[10px] font-medium tracking-[0.08em] text-toptrader-muted">{label}</p>
      <p className="mt-1 text-[15px] font-semibold leading-5 tracking-tight text-toptrader-ink">{value}</p>
      {helper ? <p className="mt-1 text-[10px] leading-4 text-toptrader-muted">{helper}</p> : null}
    </div>
  )
}
