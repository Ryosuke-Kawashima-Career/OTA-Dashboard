import type { GlobalKpis } from '../types'

export async function fetchGlobalKpis(snapshotMonth?: string | null): Promise<GlobalKpis> {
  const url = snapshotMonth
    ? `/api/kpis/global?snapshot_month=${encodeURIComponent(snapshotMonth)}`
    : '/api/kpis/global'
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to fetch global KPIs: ${response.status} ${response.statusText}`)
  }
  return (await response.json()) as GlobalKpis
}

export function exportCsvUrl(snapshotMonth?: string | null): string {
  return snapshotMonth
    ? `/api/export?snapshot_month=${encodeURIComponent(snapshotMonth)}`
    : '/api/export'
}
