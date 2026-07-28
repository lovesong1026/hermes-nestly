/** Starter model allowlist for new users (before Settings favorites). */

/** Preferred default when the user has not saved a preferred_model. */
export const STARTER_PREFERRED_MODEL = 'gpt-5.6-sol'

/** Match order for the chat picker when favorites are empty. */
const STARTER_ORDER: RegExp[] = [
  /^gpt-5\.6-sol(?:-|\/|$)/i,
  /(?:^|[-_/])opus[-_.]?4\.?8(?:[-_/]|$)/i,
  /(?:^|[-_/])sonnet[-_.]?4\.?6(?:[-_/]|$)/i,
  /deepseek.*v3\.?2/i,
  /deepseek.*v4/i,
  /gpt-image-2/i,
  /grok-imagine-video/i,
]

function bareModelId(id: string): string {
  const trimmed = id.trim()
  const slash = trimmed.lastIndexOf('/')
  return (slash >= 0 ? trimmed.slice(slash + 1) : trimmed).toLowerCase()
}

/** True when ``id`` belongs to the curated starter set. */
export function isStarterModel(id: string): boolean {
  const bare = bareModelId(id)
  const full = id.trim().toLowerCase()
  return STARTER_ORDER.some((re) => re.test(bare) || re.test(full))
}

function starterRank(id: string): number {
  const bare = bareModelId(id)
  const full = id.trim().toLowerCase()
  const idx = STARTER_ORDER.findIndex((re) => re.test(bare) || re.test(full))
  return idx >= 0 ? idx : STARTER_ORDER.length
}

/**
 * Keep only starter models from the upstream catalog, ordered for the picker.
 * Falls back to the full catalog when nothing matches (misconfigured upstream).
 */
export function filterStarterModels<T extends { id: string }>(models: T[]): T[] {
  const filtered = models.filter((m) => isStarterModel(m.id))
  if (filtered.length === 0) return models
  return [...filtered].sort((a, b) => {
    const ra = starterRank(a.id)
    const rb = starterRank(b.id)
    if (ra !== rb) return ra - rb
    return a.id.localeCompare(b.id)
  })
}

/**
 * Resolve the model to select on first chat load.
 * Prefer saved preferred → starter gpt-5.6-sol → gateway default → first picker id.
 */
export function resolveInitialModel(opts: {
  preferred?: string | null
  defaultModel?: string | null
  catalogIds: string[]
  pickerIds: string[]
}): string {
  const catalog = new Set(opts.catalogIds)
  const picker = opts.pickerIds

  const preferred = opts.preferred?.trim()
  if (preferred && catalog.has(preferred)) return preferred

  const solExact = picker.find((id) => bareModelId(id) === STARTER_PREFERRED_MODEL)
  if (solExact) return solExact
  const solPrefix = picker.find((id) =>
    bareModelId(id).startsWith(`${STARTER_PREFERRED_MODEL}-`),
  )
  if (solPrefix) return solPrefix

  const gatewayDefault = opts.defaultModel?.trim()
  if (gatewayDefault && catalog.has(gatewayDefault)) return gatewayDefault

  return picker[0] || opts.catalogIds[0] || ''
}
