export function normalizeWatchlist(raw: string) {
  const normalized = raw
    .replace(/\r\n/g, '\n')
    .replace(/[，、；;]+/g, '\n')
    .replace(/[ \t]*\n[ \t]*/g, '\n')
  const lines = normalized
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)

  const cleaned: string[] = []
  for (const line of lines) {
    const compact = line.replace(/\s+/g, ' ').trim()
    if (!compact) continue
    const canonical = compact.replace(/\s*\|\s*/g, ' | ')
    if (!cleaned.includes(canonical)) {
      cleaned.push(canonical)
    }
  }
  return cleaned.join('\n')
}
