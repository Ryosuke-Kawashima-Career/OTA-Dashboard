import { create } from 'zustand'

import { fetchSnapshots } from '../api/snapshots'

interface TimePeriodState {
  // ISO YYYY-MM-DD strings, sorted ascending. Empty until loadSnapshots resolves.
  available: string[]
  selected: string | null
  loaded: boolean
  error: string | null
  loadSnapshots: () => Promise<void>
  setSelected: (snapshot: string) => void
}

export const useTimePeriodStore = create<TimePeriodState>((set) => ({
  available: [],
  selected: null,
  loaded: false,
  error: null,
  loadSnapshots: async () => {
    try {
      const data = await fetchSnapshots()
      set({
        available: data.months,
        // Default to the latest month so the dashboard mirrors the
        // original "latest snapshot" behavior on first paint.
        selected: data.latest ?? null,
        loaded: true,
        error: null,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      set({ error: message, loaded: true })
    }
  },
  setSelected: (snapshot) => set({ selected: snapshot }),
}))
