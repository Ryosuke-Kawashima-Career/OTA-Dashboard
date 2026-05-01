import { useEffect, useMemo, useState, type ChangeEvent } from 'react'

import { fetchRegions } from '../api/regions'
import { useComparisonStore } from '../stores/comparisonStore'
import { useTimePeriodStore } from '../stores/timePeriodStore'

interface RegionOption {
  iso_code: string
  name: string
}

export function ComparisonPicker() {
  const [options, setOptions] = useState<RegionOption[]>([])
  const selectedIsos = useComparisonStore((s) => s.selectedIsos)
  const addRegion = useComparisonStore((s) => s.addRegion)
  const removeRegion = useComparisonStore((s) => s.removeRegion)
  const clear = useComparisonStore((s) => s.clear)
  const selectedSnapshot = useTimePeriodStore((s) => s.selected)

  useEffect(() => {
    let cancelled = false
    fetchRegions()
      .then((collection) => {
        if (cancelled) return
        // Only include regions that have a seeded demand_index — comparing
        // empty rows is meaningless and clutters the dropdown.
        const seeded = collection.features
          .filter((f) => f.properties.iso_code && f.properties.demand_index !== null)
          .map((f) => ({
            iso_code: f.properties.iso_code,
            name: f.properties.name ?? f.properties.iso_code,
          }))
          .sort((a, b) => a.name.localeCompare(b.name))
        setOptions(seeded)
      })
      .catch(() => {
        // The world-map view already surfaces /api/regions errors; no need
        // to double-render the failure here.
      })
    return () => {
      cancelled = true
    }
  }, [])

  const availableOptions = useMemo(
    () => options.filter((o) => !selectedIsos.includes(o.iso_code)),
    [options, selectedIsos],
  )

  const onSelect = (event: ChangeEvent<HTMLSelectElement>) => {
    const iso = event.target.value
    event.target.value = ''
    if (!iso) return
    void addRegion(iso, selectedSnapshot)
  }

  const labelById = useMemo(() => {
    const map = new Map<string, string>()
    for (const o of options) map.set(o.iso_code, o.name)
    return map
  }, [options])

  return (
    <div className="comparison-picker" role="group" aria-label="Region comparison picker">
      <span className="comparison-picker__label">Compare</span>
      <div className="comparison-picker__chips">
        {selectedIsos.map((iso) => (
          <span key={iso} className="comparison-picker__chip">
            {labelById.get(iso) ?? iso}
            <button
              type="button"
              className="comparison-picker__chip-remove"
              aria-label={`Remove ${labelById.get(iso) ?? iso} from comparison`}
              onClick={() => removeRegion(iso)}
            >
              ×
            </button>
          </span>
        ))}
        {selectedIsos.length === 0 && (
          <span className="comparison-picker__placeholder">
            pick regions to compare
          </span>
        )}
      </div>
      <select
        className="comparison-picker__select"
        defaultValue=""
        onChange={onSelect}
        disabled={availableOptions.length === 0}
        aria-label="Add region to comparison"
      >
        <option value="" disabled>
          {availableOptions.length === 0 ? 'All regions selected' : '+ Add region'}
        </option>
        {availableOptions.map((o) => (
          <option key={o.iso_code} value={o.iso_code}>
            {o.name}
          </option>
        ))}
      </select>
      {selectedIsos.length > 0 && (
        <button
          type="button"
          className="comparison-picker__clear"
          onClick={clear}
          aria-label="Clear comparison selection"
        >
          Clear
        </button>
      )}
    </div>
  )
}
