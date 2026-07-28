import { filterStarterModels } from './modelStarter'

/** Fired when Settings saves workspace model preferences. */
export const PREFERENCES_UPDATED_EVENT = 'hermes:preferences-updated'

/**
 * Prefer favorite models in the chat picker.
 * When favorites are empty (new user), show the curated starter set instead
 * of the full upstream catalog. Falls back to full catalog only if the
 * starter filter matches nothing.
 */
export function filterModelsByFavorites<T extends { id: string }>(
  models: T[],
  favorites: string[] | null | undefined,
  alwaysInclude?: string | null,
): T[] {
  if (!favorites?.length) {
    const starter = filterStarterModels(models)
    const extra = alwaysInclude?.trim()
    if (!extra || starter.some((m) => m.id === extra)) return starter
    const found = models.find((m) => m.id === extra)
    return found ? [...starter, found] : starter
  }
  const set = new Set(favorites)
  const extra = alwaysInclude?.trim()
  if (extra) set.add(extra)
  const filtered = models.filter((m) => set.has(m.id))
  return filtered.length > 0 ? filtered : models
}

export function notifyPreferencesUpdated() {
  window.dispatchEvent(new CustomEvent(PREFERENCES_UPDATED_EVENT))
}
