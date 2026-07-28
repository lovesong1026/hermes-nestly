/**
 * Usage Center charts — Chart.js via react-chartjs-2.
 * Canvas 不支持 CSS 变量，颜色用固定 palette（与主题 chart token 近似）。
 */
import { useMemo } from 'react'
import {
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  DoughnutController,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Tooltip,
  type ChartData,
  type ChartOptions,
} from 'chart.js'
import { Bar, Doughnut } from 'react-chartjs-2'
import { useT } from '../i18n'
import type { UsageLogDailyPoint, UsageLogModelRow } from '../platformClient'

// 混合柱+折线需要同时注册 BarController 与 LineController
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarController,
  BarElement,
  LineController,
  LineElement,
  PointElement,
  DoughnutController,
  ArcElement,
  Tooltip,
  Legend,
)

const MODEL_COLORS = [
  '#0f766e',
  '#5eead4',
  '#6366f1',
  '#f59e0b',
  '#ec4899',
  '#84cc16',
  '#0ea5e9',
  '#a78bfa',
]

function colorForModel(index: number): string {
  return MODEL_COLORS[index % MODEL_COLORS.length] ?? MODEL_COLORS[0]
}

export function DailyTrendChart({
  daily,
  models,
}: {
  daily: UsageLogDailyPoint[]
  models: UsageLogModelRow[]
}) {
  const t = useT()
  const modelOrder = models.map((m) => m.model)

  const data = useMemo<ChartData<'bar'>>(() => {
    const labels = daily.map((d) => d.date.slice(5))
    const stackModels =
      modelOrder.length > 0
        ? modelOrder
        : Array.from(
            new Set(daily.flatMap((d) => Object.keys(d.by_model))),
          )

    const barDatasets = stackModels.map((model, i) => ({
      type: 'bar' as const,
      label: model,
      data: daily.map((d) => d.by_model[model] ?? 0),
      backgroundColor: colorForModel(i),
      borderSkipped: false as const,
      stack: 'cost',
      yAxisID: 'y',
      order: 2,
    }))

    const lineDataset = {
      type: 'line' as const,
      label: t('usage.stat.requests'),
      data: daily.map((d) => d.requests),
      borderColor: 'rgba(15, 23, 42, 0.65)',
      backgroundColor: 'rgba(15, 23, 42, 0.65)',
      pointRadius: 3,
      pointHoverRadius: 4,
      tension: 0.25,
      yAxisID: 'y1',
      order: 1,
    }

    return {
      labels,
      // Mixed bar + line: Chart.js accepts heterogeneous dataset types.
      datasets: [...barDatasets, lineDataset] as ChartData<'bar'>['datasets'],
    }
  }, [daily, modelOrder, t])

  const options = useMemo<ChartOptions<'bar'>>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'bottom',
          labels: { boxWidth: 10, boxHeight: 10, font: { size: 11 } },
        },
        tooltip: {
          callbacks: {
            label(ctx) {
              const label = ctx.dataset.label ?? ''
              const v = ctx.parsed.y
              if (v == null) return label
              if (ctx.dataset.yAxisID === 'y1') {
                return `${label}: ${v}`
              }
              return `${label}: $${Number(v).toFixed(4)}`
            },
          },
        },
      },
      scales: {
        x: {
          stacked: true,
          grid: { display: false },
          ticks: { maxRotation: 0, autoSkip: true, font: { size: 10 } },
        },
        y: {
          stacked: true,
          position: 'left',
          title: { display: true, text: 'USD', font: { size: 11 } },
          ticks: {
            callback: (v) => `$${Number(v).toFixed(2)}`,
            font: { size: 10 },
          },
        },
        y1: {
          position: 'right',
          grid: { drawOnChartArea: false },
          title: {
            display: true,
            text: t('usage.stat.requests'),
            font: { size: 11 },
          },
          ticks: { precision: 0, font: { size: 10 } },
          beginAtZero: true,
        },
      },
    }),
    [t],
  )

  return (
    <div
      className="h-64 w-full min-w-0"
      role="img"
      aria-label={t('usage.trend.title')}
    >
      <Bar data={data} options={options} />
    </div>
  )
}

export function ModelDonut({ models }: { models: UsageLogModelRow[] }) {
  const t = useT()

  const data = useMemo<ChartData<'doughnut'>>(
    () => ({
      labels: models.map((m) => m.model),
      datasets: [
        {
          data: models.map((m) => m.cost_usd),
          backgroundColor: models.map((_, i) => colorForModel(i)),
          borderWidth: 0,
          hoverOffset: 4,
        },
      ],
    }),
    [models],
  )

  const options = useMemo<ChartOptions<'doughnut'>>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      cutout: '62%',
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label(ctx) {
              const label = ctx.label ?? ''
              const v = ctx.parsed
              return `${label}: $${Number(v).toFixed(4)}`
            },
          },
        },
      },
    }),
    [],
  )

  return (
    <div className="flex justify-center">
      <div
        className="size-48"
        role="img"
        aria-label={t('usage.models.distribution')}
      >
        {models.length === 0 ? (
          <div className="size-full rounded-full border-8 border-muted" />
        ) : (
          <Doughnut data={data} options={options} />
        )}
      </div>
    </div>
  )
}
