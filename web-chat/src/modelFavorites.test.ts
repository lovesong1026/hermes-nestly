import { describe, expect, it } from 'vitest'

import { filterModelsByFavorites } from './modelFavorites'

describe('filterModelsByFavorites', () => {
  const catalog = [
    { id: 'gpt-5.6-sol' },
    { id: 'claude-opus-4.8' },
    { id: 'gpt-5.6-luna' },
    { id: 'claude-sonnet-4.6' },
  ]

  it('uses starter allowlist when favorites empty', () => {
    expect(filterModelsByFavorites(catalog, []).map((m) => m.id)).toEqual([
      'gpt-5.6-sol',
      'claude-opus-4.8',
      'claude-sonnet-4.6',
    ])
    expect(filterModelsByFavorites(catalog, null).map((m) => m.id)).toEqual([
      'gpt-5.6-sol',
      'claude-opus-4.8',
      'claude-sonnet-4.6',
    ])
  })

  it('keeps only favorite ids when present in catalog', () => {
    expect(
      filterModelsByFavorites(catalog, ['claude-sonnet-4.6', 'gpt-5.6-sol']),
    ).toEqual([{ id: 'gpt-5.6-sol' }, { id: 'claude-sonnet-4.6' }])
  })

  it('falls back to full catalog when no favorite matches', () => {
    expect(filterModelsByFavorites(catalog, ['missing'])).toEqual(catalog)
  })

  it('always includes the active model even if not favorited', () => {
    expect(
      filterModelsByFavorites(catalog, ['gpt-5.6-sol'], 'gpt-5.6-luna').map(
        (m) => m.id,
      ),
    ).toEqual(['gpt-5.6-sol', 'gpt-5.6-luna'])
  })
})
