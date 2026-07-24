import { describe, expect, it } from 'vitest'

import {
  STARTER_PREFERRED_MODEL,
  filterStarterModels,
  isStarterModel,
  resolveInitialModel,
} from './modelStarter'

describe('isStarterModel', () => {
  it('accepts curated families', () => {
    expect(isStarterModel('gpt-5.6-sol')).toBe(true)
    expect(isStarterModel('claude-opus-4.8')).toBe(true)
    expect(isStarterModel('anthropic/claude-opus-4.8-pro')).toBe(true)
    expect(isStarterModel('claude-sonnet-4.6')).toBe(true)
    expect(isStarterModel('deepseek-v3.2')).toBe(true)
    expect(isStarterModel('deepseek-v4-pro')).toBe(true)
    expect(isStarterModel('gpt-image-2')).toBe(true)
    expect(isStarterModel('gpt-image-2-medium')).toBe(true)
    expect(isStarterModel('grok-imagine-video')).toBe(true)
  })

  it('rejects unrelated catalog noise', () => {
    expect(isStarterModel('gpt-5.6-luna')).toBe(false)
    expect(isStarterModel('claude-haiku-4.5')).toBe(false)
    expect(isStarterModel('gemini-2.5-pro')).toBe(false)
  })
})

describe('filterStarterModels', () => {
  it('keeps starter ids and orders preferred families first', () => {
    const catalog = [
      { id: 'gemini-2.5-pro' },
      { id: 'grok-imagine-video' },
      { id: 'claude-sonnet-4.6' },
      { id: 'deepseek-v4-flash' },
      { id: 'gpt-5.6-sol' },
      { id: 'claude-opus-4.8' },
      { id: 'deepseek-v3.2' },
      { id: 'gpt-image-2' },
      { id: 'gpt-5.6-luna' },
    ]
    expect(filterStarterModels(catalog).map((m) => m.id)).toEqual([
      'gpt-5.6-sol',
      'claude-opus-4.8',
      'claude-sonnet-4.6',
      'deepseek-v3.2',
      'deepseek-v4-flash',
      'gpt-image-2',
      'grok-imagine-video',
    ])
  })

  it('falls back to full catalog when nothing matches', () => {
    const catalog = [{ id: 'only-weird-model' }]
    expect(filterStarterModels(catalog)).toEqual(catalog)
  })
})

describe('resolveInitialModel', () => {
  const catalog = [
    'claude-opus-4.8',
    'claude-sonnet-4.6',
    'gpt-5.6-sol',
    'gpt-image-2',
  ]

  it('uses saved preferred when present', () => {
    expect(
      resolveInitialModel({
        preferred: 'claude-sonnet-4.6',
        catalogIds: catalog,
        pickerIds: catalog,
      }),
    ).toBe('claude-sonnet-4.6')
  })

  it(`defaults to ${STARTER_PREFERRED_MODEL} before gateway default`, () => {
    expect(
      resolveInitialModel({
        preferred: null,
        defaultModel: 'claude-opus-4.8',
        catalogIds: catalog,
        pickerIds: catalog,
      }),
    ).toBe('gpt-5.6-sol')
  })
})
