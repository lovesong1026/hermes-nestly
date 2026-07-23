import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminSkillsPage } from './AdminSkillsPage'

vi.mock('../platformClient', () => ({
  PlatformApiError: class extends Error {},
  platform: {
    adminSkills: vi.fn(),
  },
}))

vi.mock('../i18n', () => ({
  useT: () => (key: string) => key,
}))

vi.mock('../routing', () => ({
  routeHref: (r: string) => `#/${r}`,
}))

import { platform } from '../platformClient'

describe('AdminSkillsPage', () => {
  beforeEach(() => {
    vi.mocked(platform.adminSkills).mockResolvedValue([
      { name: 'demo-skill', path: '/tmp/skills/demo-skill/SKILL.md' },
    ])
  })

  it('lists global skills from admin API', async () => {
    render(<AdminSkillsPage />)
    await waitFor(() => {
      expect(screen.getByText('demo-skill')).toBeInTheDocument()
    })
    expect(screen.getByText('/tmp/skills/demo-skill/SKILL.md')).toBeInTheDocument()
    expect(platform.adminSkills).toHaveBeenCalled()
  })
})
