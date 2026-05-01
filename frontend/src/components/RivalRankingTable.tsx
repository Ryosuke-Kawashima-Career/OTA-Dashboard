import type { RivalRankingEntry } from '../types'

interface Props {
  ranking: RivalRankingEntry[]
}

export function RivalRankingTable({ ranking }: Props) {
  if (ranking.length === 0) {
    return <p className="region-panel__empty">No rival snapshots seeded for this region.</p>
  }

  return (
    <table className="rival-ranking">
      <thead>
        <tr>
          <th scope="col">#</th>
          <th scope="col">Rival</th>
          <th scope="col" className="rival-ranking__num" title="Local market share">
            Share
          </th>
          <th scope="col" className="rival-ranking__num" title="Worldwide rank by booking volume">
            Global
          </th>
        </tr>
      </thead>
      <tbody>
        {ranking.map((r, idx) => (
          <tr key={r.rival_id}>
            <td className="rival-ranking__rank">{idx + 1}</td>
            <td>
              <div className="rival-ranking__name">{r.name}</div>
              {r.categories.length > 0 && (
                <div className="rival-ranking__meta">{r.categories.join(' / ')}</div>
              )}
            </td>
            <td className="rival-ranking__num">{r.market_share_pct.toFixed(1)}%</td>
            <td className="rival-ranking__num">
              {r.global_rank === null ? '—' : `#${r.global_rank}`}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
