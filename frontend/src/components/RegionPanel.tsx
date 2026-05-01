import { useEffect } from 'react'

import { useRegionDetailStore } from '../stores/regionDetailStore'
import { useTimePeriodStore } from '../stores/timePeriodStore'
import { DemandChart } from './DemandChart'
import { DemographicsDonut } from './DemographicsDonut'
import { RivalRankingTable } from './RivalRankingTable'

export function RegionPanel() {
  const selectedIso = useRegionDetailStore((s) => s.selectedIso)
  const detail = useRegionDetailStore((s) => s.detail)
  const loading = useRegionDetailStore((s) => s.loading)
  const error = useRegionDetailStore((s) => s.error)
  const closeRegion = useRegionDetailStore((s) => s.closeRegion)
  const refreshSelected = useRegionDetailStore((s) => s.refreshSelected)
  const selectedSnapshot = useTimePeriodStore((s) => s.selected)

  useEffect(() => {
    if (!selectedIso) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeRegion()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selectedIso, closeRegion])

  // When the user moves the time-period slider while a region is open, the
  // panel must re-fetch against the new snapshot. We skip the very first
  // render after open because openRegion already kicks off the right fetch.
  useEffect(() => {
    if (!selectedIso) return
    void refreshSelected(selectedSnapshot)
  }, [selectedSnapshot, selectedIso, refreshSelected])

  if (!selectedIso) return null

  return (
    <aside
      className="region-panel"
      role="dialog"
      aria-label={`${detail?.name ?? selectedIso} regional characteristics`}
    >
      <header className="region-panel__header">
        <div>
          <h2 className="region-panel__title">{detail?.name ?? selectedIso}</h2>
          <p className="region-panel__subtitle">
            {detail?.continent ?? '—'}
            {detail?.snapshot_month ? ` · snapshot ${detail.snapshot_month}` : ''}
          </p>
        </div>
        <button
          type="button"
          className="region-panel__close"
          onClick={closeRegion}
          aria-label="Close regional panel"
        >
          ×
        </button>
      </header>

      {loading && <div className="region-panel__status">Loading…</div>}
      {error && <div className="region-panel__status region-panel__status--error">{error}</div>}

      {detail && !loading && !error && (
        <>
          <section className="region-panel__kpis">
            <div>
              <div className="region-panel__kpi-label">Demand Index</div>
              <div className="region-panel__kpi-value">
                {detail.demand_index === null ? '—' : detail.demand_index}
              </div>
            </div>
            <div>
              <div className="region-panel__kpi-label">Avg Booking Value</div>
              <div className="region-panel__kpi-value">
                {detail.avg_booking_value === null
                  ? '—'
                  : `$${detail.avg_booking_value.toFixed(2)}`}
              </div>
            </div>
          </section>

          <section className="region-panel__section">
            <h3>Seasonal Demand (12 mo)</h3>
            <DemandChart series={detail.monthly_demand} />
          </section>

          <section className="region-panel__section">
            <h3>Traveler Demographics</h3>
            <DemographicsDonut segments={detail.demographics} />
          </section>

          <section className="region-panel__section">
            <h3>Top Routes</h3>
            {detail.top_routes.length === 0 ? (
              <p className="region-panel__empty">No route data seeded for this region.</p>
            ) : (
              <ul className="region-panel__routes">
                {detail.top_routes.map((r) => (
                  <li key={r.route}>
                    <span>{r.route}</span>
                    <strong>{r.share_pct.toFixed(1)}%</strong>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="region-panel__section">
            <h3>Rival Ranking</h3>
            <RivalRankingTable ranking={detail.rival_ranking} />
          </section>
        </>
      )}
    </aside>
  )
}
