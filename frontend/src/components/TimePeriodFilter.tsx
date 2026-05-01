import { useEffect } from 'react'

import { useTimePeriodStore } from '../stores/timePeriodStore'

function yearOf(snapshot: string): string {
  return snapshot.slice(0, 4)
}

export function TimePeriodFilter() {
  const available = useTimePeriodStore((s) => s.available)
  const selected = useTimePeriodStore((s) => s.selected)
  const loaded = useTimePeriodStore((s) => s.loaded)
  const error = useTimePeriodStore((s) => s.error)
  const loadSnapshots = useTimePeriodStore((s) => s.loadSnapshots)
  const setSelected = useTimePeriodStore((s) => s.setSelected)

  useEffect(() => {
    if (!loaded) void loadSnapshots()
  }, [loaded, loadSnapshots])

  if (!loaded || error || available.length === 0) {
    // Hide the control until we know the available range. The KPI/map
    // load paths handle the "no snapshot" case via their own error states.
    return null
  }

  // Single-snapshot DBs don't need a slider — drop the control rather than
  // render a draggable handle that can't move.
  if (available.length === 1) {
    return (
      <div className="time-filter time-filter--static">
        <span className="time-filter__label">Year</span>
        <span className="time-filter__value">{yearOf(available[0])}</span>
      </div>
    )
  }

  const min = 0
  const max = available.length - 1
  const currentIndex = selected ? Math.max(0, available.indexOf(selected)) : max

  return (
    <div className="time-filter" role="group" aria-label="Time period filter">
      <span className="time-filter__label">Year</span>
      <input
        type="range"
        className="time-filter__slider"
        min={min}
        max={max}
        step={1}
        value={currentIndex}
        list="time-filter-ticks"
        aria-valuetext={selected ? yearOf(selected) : undefined}
        onChange={(event) => {
          const idx = Number(event.target.value)
          const next = available[idx]
          if (next) setSelected(next)
        }}
      />
      <datalist id="time-filter-ticks">
        {available.map((m, idx) => (
          <option key={m} value={idx} label={yearOf(m)} />
        ))}
      </datalist>
      <span className="time-filter__value" aria-live="polite">
        {selected ? yearOf(selected) : '—'}
      </span>
    </div>
  )
}
