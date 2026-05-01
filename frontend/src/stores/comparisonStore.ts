import { create } from 'zustand'

import { fetchRegionDetail } from '../api/regionDetail'
import type { RegionDetail } from '../types'

interface ComparisonState {
  selectedIsos: string[]
  // Cached details are keyed by `${iso}@${snapshot ?? 'latest'}` so flipping
  // the time-period slider doesn't show stale numbers from the prior year.
  details: Record<string, RegionDetail>
  loading: Set<string>
  error: string | null
  currentSnapshot: string | null
  addRegion: (iso: string, snapshotMonth?: string | null) => Promise<void>
  removeRegion: (iso: string) => void
  refreshAll: (snapshotMonth: string | null) => Promise<void>
  clear: () => void
}

function detailKey(iso: string, snapshotMonth: string | null | undefined): string {
  return `${iso}@${snapshotMonth ?? 'latest'}`
}

async function fetchOne(
  iso: string,
  snapshotMonth: string | null | undefined,
  set: (
    partial:
      | Partial<ComparisonState>
      | ((state: ComparisonState) => Partial<ComparisonState>),
  ) => void,
  get: () => ComparisonState,
): Promise<void> {
  const key = detailKey(iso, snapshotMonth)
  const { details, loading } = get()
  if (details[key] || loading.has(key)) return
  const nextLoading = new Set(loading)
  nextLoading.add(key)
  set({ loading: nextLoading, error: null })
  try {
    const detail = await fetchRegionDetail(iso, snapshotMonth)
    const after = get()
    const cleared = new Set(after.loading)
    cleared.delete(key)
    // If the user removed the region while the request was open, just clear
    // the loading flag without writing detail — avoids resurrecting a chip.
    if (!after.selectedIsos.includes(iso)) {
      set({ loading: cleared })
      return
    }
    set({ details: { ...after.details, [key]: detail }, loading: cleared })
  } catch (err) {
    const after = get()
    const cleared = new Set(after.loading)
    cleared.delete(key)
    const message = err instanceof Error ? err.message : 'Unknown error'
    set({ loading: cleared, error: message })
  }
}

export const useComparisonStore = create<ComparisonState>((set, get) => ({
  selectedIsos: [],
  details: {},
  loading: new Set<string>(),
  error: null,
  currentSnapshot: null,
  addRegion: async (iso, snapshotMonth) => {
    const { selectedIsos } = get()
    if (selectedIsos.includes(iso)) return
    set({ selectedIsos: [...selectedIsos, iso], currentSnapshot: snapshotMonth ?? null })
    await fetchOne(iso, snapshotMonth ?? null, set, get)
  },
  removeRegion: (iso) =>
    set((state) => ({
      selectedIsos: state.selectedIsos.filter((c) => c !== iso),
    })),
  refreshAll: async (snapshotMonth) => {
    set({ currentSnapshot: snapshotMonth })
    const { selectedIsos } = get()
    await Promise.all(selectedIsos.map((iso) => fetchOne(iso, snapshotMonth, set, get)))
  },
  clear: () => set({ selectedIsos: [], error: null }),
}))
