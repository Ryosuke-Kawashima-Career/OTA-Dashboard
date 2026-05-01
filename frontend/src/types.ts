import type { FeatureCollection, MultiPolygon, Polygon } from 'geojson'

export type KpiKey = 'demand_index' | 'avg_booking_value'

export interface KpiDefinition {
  key: KpiKey
  label: string
  unit: string
  format: (value: number) => string
}

export interface RegionProperties {
  iso_code: string
  name: string
  continent: string | null
  demand_index: number | null
  avg_booking_value: number | null
  snapshot_month: string | null
}

export type RegionGeometry = Polygon | MultiPolygon
export type RegionFeatureCollection = FeatureCollection<RegionGeometry, RegionProperties>

export interface Rival {
  id: string
  name: string
  hq_country: string | null
  // Multiple categories per rival — some OTAs serve both B2C and B2B
  // (e.g. Expedia + Expedia Partner Solutions, Traveloka + Traveloka for Business).
  categories: string[]
  business_model: string | null
  ai_strategy: string | null
  website: string | null
  lat: number
  lng: number
}

export interface RivalsResponse {
  rivals: Rival[]
  count: number
}

export interface MonthlyDemandPoint {
  month: number
  value: number
}

export interface TopRoute {
  route: string
  share_pct: number
}

export interface DemographicSegment {
  segment: string
  share_pct: number
}

export interface RivalRankingEntry {
  rival_id: string
  name: string
  categories: string[]
  market_share_pct: number
  booking_volume: number | null
  // Worldwide rank by total booking_volume across all regions for the same
  // snapshot month. `null` only when the rival has no global volume that month.
  global_rank: number | null
}

export interface RegionDetail {
  iso_code: string
  name: string
  continent: string | null
  demand_index: number | null
  avg_booking_value: number | null
  snapshot_month: string | null
  monthly_demand: MonthlyDemandPoint[]
  top_routes: TopRoute[]
  demographics: DemographicSegment[]
  rival_ranking: RivalRankingEntry[]
}

export interface HottestGrowthRegion {
  iso_code: string
  name: string
  demand_index: number
}

export interface GlobalKpis {
  markets_covered: number
  tracked_rivals: number
  hottest_growth_region: HottestGrowthRegion | null
  snapshot_month: string | null
}

export interface SnapshotsResponse {
  months: string[]
  latest: string | null
}

export const KPI_DEFINITIONS: Record<KpiKey, KpiDefinition> = {
  demand_index: {
    key: 'demand_index',
    label: 'Demand Index',
    unit: '',
    format: (v) => v.toFixed(0),
  },
  avg_booking_value: {
    key: 'avg_booking_value',
    label: 'Avg Booking Value',
    unit: 'USD',
    format: (v) => `$${v.toFixed(2)}`,
  },
}
