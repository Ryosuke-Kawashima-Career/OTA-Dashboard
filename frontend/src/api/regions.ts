import type { RegionFeatureCollection } from '../types'

export async function fetchRegions(snapshotMonth?: string | null): Promise<RegionFeatureCollection> {
  const url = snapshotMonth
    ? `/api/regions?snapshot_month=${encodeURIComponent(snapshotMonth)}`
    : '/api/regions'
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to fetch regions: ${response.status} ${response.statusText}`)
  }
  return (await response.json()) as RegionFeatureCollection
}
