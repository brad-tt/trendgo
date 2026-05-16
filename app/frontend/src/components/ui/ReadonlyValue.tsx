export function ReadonlyValue({
  helper,
  value,
}: {
  helper: string
  value: number | string
}) {
  return (
    <div className="rounded-lg border border-toptrader-line bg-toptrader-soft/50 px-3 py-2.5">
      <div className="text-[13px] font-semibold text-toptrader-ink">{value}</div>
      <div className="mt-1 text-[10px] leading-4 text-toptrader-muted">{helper}</div>
    </div>
  )
}
