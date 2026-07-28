import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { PageShell } from '../components/PageShell'
import { useT } from '../i18n'
import { routeHref } from '../routing'
import {
  PlatformApiError,
  platform,
  type UsageLogDays,
  type UsageLogOverview,
  type UsageLogRow,
} from '../platformClient'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

const DAY_OPTIONS: UsageLogDays[] = [1, 3, 7, 30, 90]
const LOG_PER_PAGE_OPTIONS = [10, 20, 50] as const
type LogPerPage = (typeof LOG_PER_PAGE_OPTIONS)[number]

/** Chart.js 单独异步块，统计 Tab 渲染时再拉。 */
const DailyTrendChart = lazy(() =>
  import('./usageCharts').then((m) => ({ default: m.DailyTrendChart })),
)
const ModelDonut = lazy(() =>
  import('./usageCharts').then((m) => ({ default: m.ModelDonut })),
)

function formatUsd(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  return `$${n.toFixed(4)}`
}

function formatWhen(iso?: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function MetricCard({
  label,
  value,
  className,
}: {
  label: string
  value: string
  className?: string
}) {
  return (
    <div
      className={cn(
        'rounded-lg border bg-card/40 p-4 space-y-1 min-w-0',
        className,
      )}
    >
      <p className="text-sm text-muted-foreground truncate">{label}</p>
      <p className="text-xl font-semibold tabular-nums tracking-tight truncate">
        {value}
      </p>
    </div>
  )
}

/** 统计 Tab 加载骨架：五卡 + 趋势 + 模型分布 */
function StatsSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-live="polite">
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="rounded-lg border bg-card/40 p-4 space-y-3">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-7 w-24" />
          </div>
        ))}
      </div>
      <section className="space-y-2">
        <Skeleton className="h-5 w-36" />
        <Skeleton className="h-64 w-full" />
      </section>
      <section className="space-y-3">
        <Skeleton className="h-5 w-40" />
        <div className="flex justify-center">
          <Skeleton className="size-48 rounded-full" />
        </div>
        <div className="rounded-lg border p-3 space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-5 w-full" />
          ))}
        </div>
      </section>
    </div>
  )
}

/** 日志 Tab 加载骨架：表格行 */
function LogsSkeleton() {
  return (
    <div
      className="overflow-x-auto rounded-lg border"
      aria-busy="true"
      aria-live="polite"
    >
      <div className="bg-muted/40 px-3 py-2 flex gap-4">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-16 ml-auto" />
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-16" />
      </div>
      <div className="divide-y divide-border/60 p-3 space-y-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex gap-4 items-center">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-4 w-14 ml-auto" />
            <Skeleton className="h-4 w-14" />
            <Skeleton className="h-4 w-16" />
          </div>
        ))}
      </div>
    </div>
  )
}

export function UsagePage() {
  const t = useT()
  const [tab, setTab] = useState<'stats' | 'logs'>('stats')
  const [days, setDays] = useState<UsageLogDays>(7)
  const [overview, setOverview] = useState<UsageLogOverview | null>(null)
  const [logs, setLogs] = useState<UsageLogRow[]>([])
  const [logPage, setLogPage] = useState(1)
  const [logPerPage, setLogPerPage] = useState<LogPerPage>(20)
  const [logTotal, setLogTotal] = useState(0)
  const [logLastPage, setLogLastPage] = useState(1)
  const [busy, setBusy] = useState(false)
  const [overviewLoading, setOverviewLoading] = useState(true)
  const [logsLoading, setLogsLoading] = useState(false)
  const [needKey, setNeedKey] = useState(false)
  /** overview 未带回余额时，兜底走 /billing/usage */
  const [billingBalance, setBillingBalance] = useState<{
    usd: number | null
    unlimited: boolean
  } | null>(null)

  const reloadOverview = useCallback(async () => {
    setOverviewLoading(true)
    try {
      const data = await platform.getUsageLogOverview(days)
      setOverview(data)
      setNeedKey(false)

      if (data.balance_usd == null && !data.balance_unlimited) {
        try {
          const bill = await platform.getBillingUsage()
          if (bill.unlimited_quota) {
            setBillingBalance({ usd: null, unlimited: true })
          } else {
            setBillingBalance({
              usd: (bill.total_available ?? 0) / 500_000,
              unlimited: false,
            })
          }
        } catch {
          setBillingBalance(null)
        }
      } else {
        setBillingBalance(null)
      }
    } catch (err) {
      if (err instanceof PlatformApiError && err.status === 403) {
        setNeedKey(true)
        setOverview(null)
        return
      }
      toast.error(err instanceof PlatformApiError ? err.message : String(err))
    } finally {
      setOverviewLoading(false)
    }
  }, [days])

  const reloadLogs = useCallback(async () => {
    setLogsLoading(true)
    try {
      const data = await platform.getUsageLogLogs({
        days,
        page: logPage,
        per_page: logPerPage,
      })
      setLogs(data.items)
      setLogTotal(data.total)
      setLogLastPage(data.last_page)
      setNeedKey(false)
    } catch (err) {
      if (err instanceof PlatformApiError && err.status === 403) {
        setNeedKey(true)
        setLogs([])
        return
      }
      toast.error(err instanceof PlatformApiError ? err.message : String(err))
    } finally {
      setLogsLoading(false)
    }
  }, [days, logPage, logPerPage])

  useEffect(() => {
    void reloadOverview()
  }, [reloadOverview])

  useEffect(() => {
    if (tab === 'logs') void reloadLogs()
  }, [tab, reloadLogs])

  useEffect(() => {
    setLogPage(1)
  }, [days, logPerPage])

  const refresh = async () => {
    setBusy(true)
    try {
      await reloadOverview()
      if (tab === 'logs') await reloadLogs()
    } finally {
      setBusy(false)
    }
  }

  const balanceLabel = useMemo(() => {
    if (!overview) return '—'
    if (overview.balance_unlimited || billingBalance?.unlimited) {
      return t('usage.balance.unlimited')
    }
    const usd = overview.balance_usd ?? billingBalance?.usd
    return formatUsd(usd)
  }, [overview, billingBalance, t])

  return (
    <PageShell
      title={
        <span className="inline-flex items-center gap-2">
          {t('nav.usage')}
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="size-8"
            disabled={busy || overviewLoading}
            aria-label={t('usage.refresh')}
            onClick={() => void refresh()}
          >
            <RefreshCw
              className={cn(
                'size-4',
                (busy || overviewLoading) && 'animate-spin',
              )}
              aria-hidden
            />
          </Button>
        </span>
      }
      hint={t('usage.intro')}
      density="reading"
      constrainWidth={false}
      className="content-column"
      actions={
        <div className="flex flex-wrap gap-1">
          {DAY_OPTIONS.map((d) => (
            <Button
              key={d}
              type="button"
              size="sm"
              variant={days === d ? 'default' : 'outline'}
              onClick={() => setDays(d)}
            >
              {t(`usage.days.${d}`)}
            </Button>
          ))}
        </div>
      }
    >
      {needKey ? (
        <div className="rounded-lg border border-dashed p-6 space-y-3">
          <p className="text-sm text-muted-foreground">{t('usage.needKey')}</p>
          <Button
            type="button"
            onClick={() => {
              window.location.hash = routeHref('settings')
            }}
          >
            {t('usage.needKey.action')}
          </Button>
        </div>
      ) : (
        <Tabs
          value={tab}
          onValueChange={(v) => setTab(v as 'stats' | 'logs')}
          className="memory-center-tabs"
        >
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <TabsList variant="line" className="flex flex-wrap h-auto">
              <TabsTrigger value="stats">{t('usage.tab.stats')}</TabsTrigger>
              <TabsTrigger value="logs">{t('usage.tab.logs')}</TabsTrigger>
            </TabsList>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                window.location.hash = routeHref('chat')
              }}
            >
              {t('usage.backToChat')}
            </Button>
          </div>

          <TabsContent value="stats" className="space-y-6 mt-4">
            {overviewLoading ? (
              <StatsSkeleton />
            ) : overview ? (
              <>
                <div className="grid gap-3 grid-cols-2 lg:grid-cols-5">
                  <MetricCard
                    label={t('usage.metric.requests')}
                    value={String(overview.requests)}
                  />
                  <MetricCard
                    label={t('usage.metric.cost')}
                    value={formatUsd(overview.cost_usd)}
                  />
                  <MetricCard
                    label={t('usage.metric.balance')}
                    value={balanceLabel}
                  />
                  <MetricCard
                    label={t('usage.metric.prompt')}
                    value={overview.prompt_tokens.toLocaleString()}
                  />
                  <MetricCard
                    label={t('usage.metric.completion')}
                    value={overview.completion_tokens.toLocaleString()}
                  />
                </div>

                <section className="space-y-2">
                  <h2 className="text-base font-medium">
                    {t('usage.trend.title')}
                  </h2>
                  {overview.daily.every((d) => d.requests === 0) ? (
                    <p className="page-hint">{t('usage.empty')}</p>
                  ) : (
                    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
                      <DailyTrendChart
                        daily={overview.daily}
                        models={overview.by_model}
                      />
                    </Suspense>
                  )}
                </section>

                <section className="space-y-3">
                  <h2 className="text-base font-medium">
                    {t('usage.models.distribution')}
                  </h2>
                  <Suspense
                    fallback={
                      <div className="flex justify-center">
                        <Skeleton className="size-48 rounded-full" />
                      </div>
                    }
                  >
                    <ModelDonut models={overview.by_model} />
                  </Suspense>
                  {overview.by_model.length === 0 ? (
                    <p className="page-hint">{t('usage.empty')}</p>
                  ) : (
                    <div className="overflow-x-auto rounded-lg border">
                      <table className="w-full text-sm">
                        <thead className="bg-muted/40 text-muted-foreground">
                          <tr className="text-left">
                            <th className="px-3 py-2 font-medium">
                              {t('usage.models.col.model')}
                            </th>
                            <th className="px-3 py-2 font-medium text-right">
                              {t('usage.models.col.requests')}
                            </th>
                            <th className="px-3 py-2 font-medium text-right">
                              {t('usage.models.col.cost')}
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {overview.by_model.map((m) => (
                            <tr
                              key={m.model}
                              className="border-t border-border/60"
                            >
                              <td className="px-3 py-2">{m.model}</td>
                              <td className="px-3 py-2 text-right tabular-nums">
                                {m.requests.toLocaleString()}
                              </td>
                              <td className="px-3 py-2 text-right tabular-nums">
                                {formatUsd(m.cost_usd)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              </>
            ) : (
              <p className="page-hint">{t('usage.empty')}</p>
            )}
          </TabsContent>

          <TabsContent value="logs" className="space-y-3 mt-4">
            {logsLoading ? (
              <LogsSkeleton />
            ) : logs.length === 0 ? (
              <p className="page-hint">{t('usage.empty')}</p>
            ) : (
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/40 text-muted-foreground">
                    <tr className="text-left">
                      <th className="px-3 py-2 font-medium">
                        {t('usage.logs.col.time')}
                      </th>
                      <th className="px-3 py-2 font-medium">
                        {t('usage.logs.col.model')}
                      </th>
                      <th className="px-3 py-2 font-medium text-right">
                        {t('usage.logs.col.prompt')}
                      </th>
                      <th className="px-3 py-2 font-medium text-right">
                        {t('usage.logs.col.completion')}
                      </th>
                      <th className="px-3 py-2 font-medium text-right">
                        {t('usage.logs.col.cost')}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((row) => (
                      <tr
                        key={String(row.id)}
                        className="border-t border-border/60"
                      >
                        <td className="px-3 py-2 whitespace-nowrap">
                          {formatWhen(row.created_at)}
                        </td>
                        <td className="px-3 py-2">{row.model_name}</td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {row.prompt_tokens.toLocaleString()}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {row.completion_tokens.toLocaleString()}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {formatUsd(row.cost_usd)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {!logsLoading ? (
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-muted-foreground">
                  {t('usage.logs.page', {
                    page: logPage,
                    total: logLastPage,
                    n: logTotal,
                  })}
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <label className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                    {t('usage.logs.perPage')}
                    <select
                      className="h-8 rounded-md border bg-background px-2 text-sm text-foreground"
                      value={logPerPage}
                      aria-label={t('usage.logs.perPage')}
                      onChange={(e) => {
                        setLogPerPage(Number(e.target.value) as LogPerPage)
                      }}
                    >
                      {LOG_PER_PAGE_OPTIONS.map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                  </label>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={logPage <= 1}
                    onClick={() => setLogPage((p) => Math.max(1, p - 1))}
                  >
                    {t('usage.logs.prev')}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={logPage >= logLastPage}
                    onClick={() =>
                      setLogPage((p) => Math.min(logLastPage, p + 1))
                    }
                  >
                    {t('usage.logs.next')}
                  </Button>
                </div>
              </div>
            ) : null}
          </TabsContent>
        </Tabs>
      )}
    </PageShell>
  )
}
