import type { RegionDetail } from '../types'

export interface ComparisonRow {
  key: string
  label: string
  unit?: string
  // null means "no data" — these cells show "—" and never count as the winner.
  values: (number | null)[]
}

/**
 * Build the set of comparable metric rows from a list of region details.
 * The `details` array order defines the column order in the rendered table.
 */
export function buildComparisonRows(details: RegionDetail[]): ComparisonRow[] {
  const peakMonthly = (d: RegionDetail) =>
    d.monthly_demand.length === 0 ? null : Math.max(...d.monthly_demand.map((p) => p.value))
  const topRivalShare = (d: RegionDetail) =>
    d.rival_ranking.length === 0 ? null : d.rival_ranking[0].market_share_pct

  return [
    {
      key: 'demand_index',
      label: 'Demand Index',
      values: details.map((d) => d.demand_index),
    },
    {
      key: 'avg_booking_value',
      label: 'Avg Booking Value',
      unit: 'USD',
      values: details.map((d) => d.avg_booking_value),
    },
    {
      key: 'peak_monthly_demand',
      label: 'Peak Monthly Demand',
      values: details.map(peakMonthly),
    },
    {
      key: 'top_rival_share',
      label: 'Top Rival Share',
      unit: '%',
      values: details.map(topRivalShare),
    },
    {
      key: 'rivals_tracked',
      label: 'Rivals Tracked',
      values: details.map((d) => d.rival_ranking.length),
    },
  ]
}

/**
 * Index of the winning cell in a row, or `null` when there is nothing to
 * declare. Highest value wins. Returns `null` when:
 *   - all values are null (no data anywhere), OR
 *   - the highest value is tied across multiple cells (no single winner).
 *
 * Tied rows intentionally show no green — calling either column a winner
 * would mislead the user.
 */
export function findWinnerIndex(values: (number | null)[]): number | null {
  let best: number | null = null
  let bestIndex: number | null = null
  let tied = false
  for (let i = 0; i < values.length; i++) {
    const v = values[i]
    if (v === null || Number.isNaN(v)) continue
    if (best === null || v > best) {
      best = v
      bestIndex = i
      tied = false
    } else if (v === best) {
      tied = true
    }
  }
  if (tied) return null
  return bestIndex
}

export function formatComparisonValue(value: number | null, unit?: string): string {
  if (value === null || Number.isNaN(value)) return '—'
  if (unit === 'USD') return `$${value.toFixed(2)}`
  if (unit === '%') return `${value.toFixed(1)}%`
  // Default: integers shown plain, fractions to one decimal.
  return Number.isInteger(value) ? value.toString() : value.toFixed(1)
}
