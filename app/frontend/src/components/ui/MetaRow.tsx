export function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-px">
      <span className="text-[10px] font-semibold tracking-[0.06em] text-toptrader-muted">{label}</span>
      <span className="break-all text-[12px] leading-[1.45] text-toptrader-ink">{value}</span>
    </div>
  )
}
