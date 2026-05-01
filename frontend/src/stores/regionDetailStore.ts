import { create } from 'zustand'

import { fetchRegionDetail } from '../api/regionDetail'
import type { RegionDetail } from '../types'

interface RegionDetailState {
  selectedIso: string | null
  detail: RegionDetail | null
  loading: boolean
  error: string | null
  openRegion: (iso: string, snapshotMonth?: string | null) => Promise<void>
  refreshSelected: (snapshotMonth: string | null) => Promise<void>
  closeRegion: () => void
}

export const useRegionDetailStore = create<RegionDetailState>((set, get) => ({
  selectedIso: null,
  detail: null,
  loading: false,
  error: null,
  openRegion: async (iso, snapshotMonth) => {
    // Always re-fetch when the user clicks a region: detail is keyed by
    // (iso, snapshot_month) and we want the freshest data even when the
    // same iso is reopened with a different time period selected.
    set({ selectedIso: iso, loading: true, error: null, detail: null })
    try {
      const detail = await fetchRegionDetail(iso, snapshotMonth)
      if (get().selectedIso !== iso) return
      set({ detail, loading: false })
    } catch (err) {
      if (get().selectedIso !== iso) return
      const message = err instanceof Error ? err.message : 'Unknown error'
      set({ error: message, loading: false })
    }
  },
  refreshSelected: async (snapshotMonth) => {
    const iso = get().selectedIso
    if (!iso) return
    set({ loading: true, error: null })
    try {
      const detail = await fetchRegionDetail(iso, snapshotMonth)
      if (get().selectedIso !== iso) return
      set({ detail, loading: false })
    } catch (err) {
      if (get().selectedIso !== iso) return
      const message = err instanceof Error ? err.message : 'Unknown error'
      set({ error: message, loading: false })
    }
  },
  closeRegion: () => set({ selectedIso: null, detail: null, loading: false, error: null }),
}))
