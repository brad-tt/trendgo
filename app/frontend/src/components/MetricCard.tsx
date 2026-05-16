export function MetricCard({
  accent = false,
  helper,
  label,
  value,
}: {
  accent?: boolean
  helper?: string
  label: string
  value: string | number
}) {
  return (
    <div
      className={[
        'relative overflow-hidden rounded-xl border px-4 py-4 shadow-[0_10px_24px_rgba(24,32,47,0.08)]',
        accent
          ? 'border-teal-100 bg-gradient-to-br from-white to-teal-50 text-toptrader-accent'
          : 'border-toptrader-line bg-white text-toptrader-accent',
      ].join(' ')}
    >
      <div
        className={[
          'absolute inset-x-0 top-0 h-1',
          accent ? 'bg-gradient-to-r from-teal-500 to-sky-500' : 'bg-gradient-to-r from-sky-200 to-teal-200',
        ].join(' ')}
      />
      <div className="flex items-center gap-3">
        <div
          className={[
            'grid h-9 w-9 shrink-0 place-items-center rounded-lg text-xs font-black',
            accent ? 'bg-teal-500 text-white' : 'bg-sky-50 text-sky-600',
          ].join(' ')}
        >
          {label.slice(0, 1)}
        </div>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold tracking-[0.08em] text-toptrader-muted">{label}</p>
          <p className="mt-1 truncate text-xl font-bold text-toptrader-accent">{value}</p>
          {helper ? <p className="mt-1 text-[11px] leading-4 text-toptrader-muted">{helper}</p> : null}
        </div>
      </div>
    </div>
  )
}
