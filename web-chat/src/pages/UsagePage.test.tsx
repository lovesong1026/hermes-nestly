import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { LocaleProvider } from '../i18n'
import { PlatformApiError, platform } from '../platformClient'
import { UsagePage } from './UsagePage'

vi.mock('../platformClient', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../platformClient')>()
  return {
    ...actual,
    platform: {
      ...actual.platform,
      getUsageLogOverview: vi.fn(),
      getUsageLogLogs: vi.fn(),
      getBillingUsage: vi.fn(),
    },
  }
})

/** jsdom 无真实 canvas —— 用占位图验证图表区域挂载。 */
vi.mock('react-chartjs-2', () => ({
  Bar: () => <canvas data-testid="usage-trend-chart" />,
  Doughnut: () => <canvas data-testid="usage-donut-chart" />,
}))

const overviewFixture = {
  days: 7 as const,
  requests: 100,
  cost_usd: 0.2594,
  balance_usd: 43.2983,
  balance_unlimited: false,
  prompt_tokens: 803452,
  completion_tokens: 24599,
  daily: [
    {
      date: '2026-07-17',
      requests: 10,
      cost_usd: 0.05,
      by_model: { 'gpt-5.6-luna': 0.05 },
    },
    {
      date: '2026-07-18',
      requests: 90,
      cost_usd: 0.2094,
      by_model: { 'gpt-5.6-luna': 0.2094 },
    },
  ],
  by_model: [
    { model: 'gpt-5.6-luna', requests: 95, cost_usd: 0.1779 },
    { model: 'deepseek-v4', requests: 5, cost_usd: 0.0815 },
  ],
}

describe('Usage Center (log API)', () => {
  beforeEach(() => {
    localStorage.setItem('hermes-locale', 'en')
    vi.mocked(platform.getUsageLogOverview).mockResolvedValue(overviewFixture)
    vi.mocked(platform.getUsageLogLogs).mockResolvedValue({
      days: 7,
      current_page: 1,
      per_page: 20,
      total: 1,
      last_page: 1,
      items: [
        {
          id: 42,
          created_at: '2026-07-18T12:00:00Z',
          model_name: 'gpt-5.6-luna',
          prompt_tokens: 100,
          completion_tokens: 20,
          quota: 500,
          cost_usd: 0.001,
        },
      ],
    })
    vi.mocked(platform.getBillingUsage).mockResolvedValue({
      total_available: 500_000,
      unlimited_quota: false,
    })
  })

  it('shows skeleton while overview is loading', async () => {
    let resolveOverview!: (v: typeof overviewFixture) => void
    vi.mocked(platform.getUsageLogOverview).mockReturnValue(
      new Promise((resolve) => {
        resolveOverview = resolve
      }),
    )

    render(
      <LocaleProvider>
        <UsagePage />
      </LocaleProvider>,
    )

    expect(
      await screen.findByRole('heading', { name: /usage center/i }),
    ).toBeInTheDocument()
    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(
      0,
    )
    expect(screen.queryByText('Total requests')).not.toBeInTheDocument()

    resolveOverview(overviewFixture)
    expect(await screen.findByText('Total requests')).toBeInTheDocument()
    await waitFor(() => {
      expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBe(0)
    })
  })

  it('shows five metric cards, Chart.js trend/donut, refresh icon, and back on tabs row', async () => {
    const user = userEvent.setup()
    render(
      <LocaleProvider>
        <UsagePage />
      </LocaleProvider>,
    )

    expect(
      await screen.findByRole('heading', { name: /usage center/i }),
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(platform.getUsageLogOverview).toHaveBeenCalledWith(7)
    })

    expect(await screen.findByText('Total requests')).toBeInTheDocument()
    expect(screen.getByText('100')).toBeInTheDocument()
    expect(screen.getByText('$0.2594')).toBeInTheDocument()
    expect(screen.getByText('$43.2983')).toBeInTheDocument()
    expect(screen.getByText('803,452')).toBeInTheDocument()
    expect(screen.getByText('24,599')).toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: /refresh|刷新/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /back to chat|返回对话/i }),
    ).toBeInTheDocument()

    expect(screen.getByText(/daily spend trend/i)).toBeInTheDocument()
    expect(screen.getByTestId('usage-trend-chart')).toBeInTheDocument()
    expect(screen.getByText(/model distribution/i)).toBeInTheDocument()
    expect(screen.getByTestId('usage-donut-chart')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /^model$/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /^requests$/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /^cost$/i })).toBeInTheDocument()
    expect(screen.getAllByText('gpt-5.6-luna').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('tab', { name: /^logs$/i }))
    await waitFor(() => {
      expect(platform.getUsageLogLogs).toHaveBeenCalled()
    })
    expect(platform.getUsageLogLogs).toHaveBeenCalledWith(
      expect.objectContaining({ per_page: 20 }),
    )
    expect(await screen.findByText('$0.0010')).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'gpt-5.6-luna' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /^input$/i })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /^output$/i })).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText(/per page/i), '50')
    await waitFor(() => {
      expect(platform.getUsageLogLogs).toHaveBeenCalledWith(
        expect.objectContaining({ per_page: 50, page: 1 }),
      )
    })
  })

  it('shows logs skeleton while logs are loading', async () => {
    const user = userEvent.setup()
    let resolveLogs!: (v: Awaited<ReturnType<typeof platform.getUsageLogLogs>>) => void
    vi.mocked(platform.getUsageLogLogs).mockReturnValue(
      new Promise((resolve) => {
        resolveLogs = resolve
      }),
    )

    render(
      <LocaleProvider>
        <UsagePage />
      </LocaleProvider>,
    )
    expect(await screen.findByText('Total requests')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /^logs$/i }))
    await waitFor(() => {
      expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(
        0,
      )
    })
    expect(screen.queryByText(/no usage records/i)).not.toBeInTheDocument()

    resolveLogs({
      days: 7,
      current_page: 1,
      per_page: 20,
      total: 0,
      last_page: 1,
      items: [],
    })
    expect(await screen.findByText(/no usage records/i)).toBeInTheDocument()
  })

  it('prompts to bind key when overview returns 403', async () => {
    vi.mocked(platform.getUsageLogOverview).mockRejectedValue(
      new PlatformApiError('upstream key not bound', 403),
    )
    render(
      <LocaleProvider>
        <UsagePage />
      </LocaleProvider>,
    )
    expect(
      await screen.findByText(/bind an upstream api key/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /open settings/i }),
    ).toBeInTheDocument()
  })
})
