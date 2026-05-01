import { describe, expect, it } from 'vitest'

import type { RegionDetail } from '../types'
import { buildComparisonRows, findWinnerIndex, formatComparisonValue } from './comparison'

const region = (overrides: Partial<RegionDetail> = {}): RegionDetail => ({
  iso_code: 'XX',
  name: 'Region X',
  continent: 'Europe',
  demand_index: 50,
  avg_booking_value: 100,
  snapshot_month: '2026-01-01',
  monthly_demand: [{ month: 7, value: 60 }],
  top_routes: [],
  demographics: [],
  rival_ranking: [],
  ...overrides,
})

describe('findWinnerIndex', () => {
  it('returns the index of the maximum value', () => {
    expect(findWinnerIndex([10, 30, 20])).toBe(1)
  })

  it('skips null and NaN entries', () => {
    expect(findWinnerIndex([null, 5, NaN, 10])).toBe(3)
  })

  it('returns null when every value is null/NaN', () => {
    expect(findWinnerIndex([null, NaN, null])).toBeNull()
  })

  it('returns null on a tie for the top spot', () => {
    expect(findWinnerIndex([20, 20, 10])).toBeNull()
  })

  it('returns a winner when a tie occurs below the max', () => {
    expect(findWinnerIndex([10, 10, 30])).toBe(2)
  })

  it('handles a single-region selection', () => {
    expect(findWinnerIndex([42])).toBe(0)
  })
})

describe('formatComparisonValue', () => {
  it('renders USD with two decimals', () => {
    expect(formatComparisonValue(42, 'USD')).toBe('$42.00')
  })

  it('renders percentages with one decimal', () => {
    expect(formatComparisonValue(33.333, '%')).toBe('33.3%')
  })

  it('renders integers without decimals when no unit applies', () => {
    expect(formatComparisonValue(7)).toBe('7')
  })

  it('renders fractions with one decimal when no unit applies', () => {
    expect(formatComparisonValue(7.25)).toBe('7.3')
  })

  it('renders an em-dash for null/NaN', () => {
    expect(formatComparisonValue(null)).toBe('—')
    expect(formatComparisonValue(NaN, 'USD')).toBe('—')
  })
})

describe('buildComparisonRows', () => {
  it('emits one row per metric in column order', () => {
    const a = region({
      iso_code: 'A',
      demand_index: 70,
      avg_booking_value: 200,
      monthly_demand: [
        { month: 1, value: 40 },
        { month: 7, value: 90 },
      ],
      rival_ranking: [
        { rival_id: '1', name: 'Rival One', categories: ['B2C'], market_share_pct: 35, booking_volume: 1000, global_rank: 1 },
        { rival_id: '2', name: 'Rival Two', categories: ['B2B'], market_share_pct: 20, booking_volume: 500, global_rank: 2 },
      ],
    })
    const b = region({
      iso_code: 'B',
      demand_index: 60,
      avg_booking_value: 250,
      monthly_demand: [{ month: 7, value: 85 }],
      rival_ranking: [],
    })

    const rows = buildComparisonRows([a, b])
    expect(rows.map((r) => r.key)).toEqual([
      'demand_index',
      'avg_booking_value',
      'peak_monthly_demand',
      'top_rival_share',
      'rivals_tracked',
    ])
    expect(rows[0].values).toEqual([70, 60])
    expect(rows[1].values).toEqual([200, 250])
    expect(rows[2].values).toEqual([90, 85])
    expect(rows[3].values).toEqual([35, null])
    expect(rows[4].values).toEqual([2, 0])
  })

  it('marks the winner in each row consistently with findWinnerIndex', () => {
    const a = region({ iso_code: 'A', demand_index: 80, avg_booking_value: 100 })
    const b = region({ iso_code: 'B', demand_index: 60, avg_booking_value: 250 })
    const rows = buildComparisonRows([a, b])
    expect(findWinnerIndex(rows[0].values)).toBe(0) // Demand winner: A
    expect(findWinnerIndex(rows[1].values)).toBe(1) // Booking winner: B
  })
})
