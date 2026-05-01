import L from 'leaflet'
import type { Feature } from 'geojson'
import { useEffect, useMemo, useRef, useState } from 'react'
import { GeoJSON, MapContainer, TileLayer } from 'react-leaflet'

import { fetchRegions } from '../api/regions'
import { RivalMarkersLayer } from './RivalMarkersLayer'
import { useKpiStore } from '../stores/kpiStore'
import { useRegionDetailStore } from '../stores/regionDetailStore'
import { useTimePeriodStore } from '../stores/timePeriodStore'
import {
  KPI_DEFINITIONS,
  type RegionFeatureCollection,
  type RegionGeometry,
  type RegionProperties,
} from '../types'
import { computeExtent, kpiColor } from '../utils/colorScale'

const OSM_TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

type RegionFeature = Feature<RegionGeometry, RegionProperties>

function renderTooltipHtml(props: RegionProperties, kpiLabel: string, kpiValue: string): string {
  const name = props.name ?? props.iso_code
  const continent = props.continent ? `<div class="tooltip__meta">${props.continent}</div>` : ''
  return `
    <div class="tooltip">
      <div class="tooltip__title">${name}</div>
      ${continent}
      <div class="tooltip__kpi"><span>${kpiLabel}:</span> <strong>${kpiValue}</strong></div>
    </div>
  `
}

export function WorldMap() {
  const selectedKpi = useKpiStore((s) => s.selectedKpi)
  const openRegion = useRegionDetailStore((s) => s.openRegion)
  const selectedSnapshot = useTimePeriodStore((s) => s.selected)
  const [data, setData] = useState<RegionFeatureCollection | null>(null)
  const [error, setError] = useState<string | null>(null)
  const geoJsonRef = useRef<L.GeoJSON | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchRegions(selectedSnapshot)
      .then((json) => {
        if (!cancelled) setData(json)
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : 'Unknown error'
          setError(message)
        }
      })
    return () => {
      cancelled = true
    }
  }, [selectedSnapshot])

  const extent = useMemo(() => {
    if (!data) return null
    const values = data.features.map((f) => f.properties[selectedKpi])
    return computeExtent(values)
  }, [data, selectedKpi])

  const kpiDef = KPI_DEFINITIONS[selectedKpi]

  const styleFeature = (feature?: RegionFeature): L.PathOptions => {
    const value = feature?.properties[selectedKpi] ?? null
    const fill = extent ? kpiColor(value, extent) : kpiColor(null, { min: 0, max: 1 })
    return {
      fillColor: fill,
      fillOpacity: value === null ? 0.5 : 0.85,
      color: '#334155',
      weight: 0.4,
    }
  }

  const onEachFeature = (feature: RegionFeature, layer: L.Layer) => {
    const props = feature.properties
    const value = props[selectedKpi]
    const kpiValue = value === null || value === undefined ? '—' : kpiDef.format(value)
    layer.bindTooltip(renderTooltipHtml(props, kpiDef.label, kpiValue), {
      sticky: true,
      direction: 'auto',
      className: 'region-tooltip',
      opacity: 1,
    })

    const pathLayer = layer as L.Path
    layer.on({
      mouseover: () => {
        pathLayer.setStyle({ weight: 2, color: '#0f172a' })
        pathLayer.bringToFront()
      },
      mouseout: () => {
        if (geoJsonRef.current) {
          geoJsonRef.current.resetStyle(pathLayer)
        }
      },
      click: () => {
        if (props.iso_code) {
          void openRegion(props.iso_code, selectedSnapshot)
        }
      },
    })
  }

  // Re-mount the GeoJSON layer when KPI or snapshot changes so styles,
  // tooltips, and click handlers (which close over selectedSnapshot) all
  // observe the latest values.
  const layerKey = `${selectedKpi}-${selectedSnapshot ?? 'none'}-${data?.features.length ?? 0}`

  return (
    <div className="world-map">
      {error && <div className="world-map__error">Failed to load regions: {error}</div>}
      <MapContainer
        center={[20, 0]}
        zoom={2}
        minZoom={2}
        maxZoom={10}
        worldCopyJump
        scrollWheelZoom
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer url={OSM_TILE_URL} attribution={OSM_ATTRIBUTION} noWrap={false} />
        {data && (
          <GeoJSON
            key={layerKey}
            ref={(instance) => {
              geoJsonRef.current = instance
            }}
            data={data}
            style={styleFeature as L.StyleFunction}
            onEachFeature={onEachFeature as L.GeoJSONOptions['onEachFeature']}
          />
        )}
        <RivalMarkersLayer />
      </MapContainer>
    </div>
  )
}
