export function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return <p className="text-sm text-toptrader-rose">{message}</p>
}
