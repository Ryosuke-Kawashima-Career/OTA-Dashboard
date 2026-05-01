import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'

import L from 'leaflet'
import 'leaflet.markercluster'
import { useEffect, useMemo, useRef } from 'react'
import { useMap } from 'react-leaflet'

import { useRivalStore } from '../stores/rivalStore'
import type { Rival } from '../types'

// Single-page-visible pin icon, inline SVG so we don't ship a binary asset.
// Chroma = Tailwind violet-600 (#7c3aed) to contrast cleanly against the
// sky-100→sky-600 choropleth from Phase 1.
const RIVAL_PIN = L.divIcon({
  className: 'rival-pin',
  html: `
    <svg viewBox="0 0 24 32" width="22" height="30" aria-hidden="true">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 8 12 20 12 20s12-12 12-20C24 5.37 18.63 0 12 0z" fill="#7c3aed" stroke="#ffffff" stroke-width="1.5"/>
      <circle cx="12" cy="12" r="4.5" fill="#ffffff"/>
    </svg>
  `,
  iconSize: [22, 30],
  iconAnchor: [11, 30],
})

function buildMarker(rival: Rival, onSelect: (id: string) => void): L.Marker {
  const marker = L.marker([rival.lat, rival.lng], { icon: RIVAL_PIN, title: rival.name })
  marker.bindTooltip(rival.name, { direction: 'top', offset: [0, -26], className: 'rival-tooltip' })
  marker.on('click', () => onSelect(rival.id))
  return marker
}

export function RivalMarkersLayer() {
  const map = useMap()
  const rivals = useRivalStore((s) => s.rivals)
  const activeCategories = useRivalStore((s) => s.activeCategories)
  const selectRival = useRivalStore((s) => s.selectRival)
  const clusterGroupRef = useRef<L.MarkerClusterGroup | null>(null)

  // A rival is visible when *any* of its categories is currently active —
  // overlap semantics mirror the backend's array-overlap filter.
  const visibleRivals = useMemo(
    () =>
      rivals.filter(
        (r) =>
          r.categories.length === 0 ||
          r.categories.some((c) => activeCategories.has(c)),
      ),
    [rivals, activeCategories],
  )

  useEffect(() => {
    const cluster = L.markerClusterGroup({
      // Phase 2 acceptance: "No overlap at zoom < 5". Cluster-radius covers
      // the largest screen pixel footprint at zoom 4 (world-continental view).
      maxClusterRadius: (zoom: number) => (zoom < 5 ? 80 : 40),
      showCoverageOnHover: false,
      spiderfyOnMaxZoom: true,
      disableClusteringAtZoom: 6,
    })
    clusterGroupRef.current = cluster
    map.addLayer(cluster)
    return () => {
      map.removeLayer(cluster)
      clusterGroupRef.current = null
    }
  }, [map])

  useEffect(() => {
    const cluster = clusterGroupRef.current
    if (!cluster) return
    cluster.clearLayers()
    for (const rival of visibleRivals) {
      cluster.addLayer(buildMarker(rival, selectRival))
    }
  }, [visibleRivals, selectRival])

  return null
}
