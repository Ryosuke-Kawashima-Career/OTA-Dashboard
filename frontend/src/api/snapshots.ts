import type { SnapshotsResponse } from '../types'

export async function fetchSnapshots(): Promise<SnapshotsResponse> {
  const response = await fetch('/api/snapshots')
  if (!response.ok) {
    throw new Error(`Failed to fetch snapshots: ${response.status} ${response.statusText}`)
  }
  return (await response.json()) as SnapshotsResponse
}
