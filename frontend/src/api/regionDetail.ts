import type { RegionDetail } from '../types'

export async function fetchRegionDetail(
  isoCode: string,
  snapshotMonth?: string | null,
): Promise<RegionDetail> {
  const params = snapshotMonth ? `?snapshot_month=${encodeURIComponent(snapshotMonth)}` : ''
  const response = await fetch(`/api/regions/${encodeURIComponent(isoCode)}${params}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch region ${isoCode}: ${response.status} ${response.statusText}`)
  }
  return (await response.json()) as RegionDetail
}
