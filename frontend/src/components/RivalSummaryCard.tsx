import { useEffect } from 'react'

import { useRivalStore } from '../stores/rivalStore'

export function RivalSummaryCard() {
  const rivals = useRivalStore((s) => s.rivals)
  const selectedRivalId = useRivalStore((s) => s.selectedRivalId)
  const selectRival = useRivalStore((s) => s.selectRival)
  const rival = rivals.find((r) => r.id === selectedRivalId) ?? null

  useEffect(() => {
    if (!rival) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') selectRival(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [rival, selectRival])

  if (!rival) return null

  return (
    <aside className="rival-card" role="dialog" aria-label={`${rival.name} summary`}>
      <header className="rival-card__header">
        <div>
          <h2 className="rival-card__title">{rival.name}</h2>
          <p className="rival-card__subtitle">
            {rival.hq_country ?? 'Unknown HQ'}
            {rival.categories.length > 0 ? ` · ${rival.categories.join(' / ')}` : ''}
          </p>
        </div>
        <button
          type="button"
          className="rival-card__close"
          onClick={() => selectRival(null)}
          aria-label="Close rival summary"
        >
          ×
        </button>
      </header>

      {rival.business_model && (
        <section className="rival-card__section">
          <h3>Business model</h3>
          <p>{rival.business_model}</p>
        </section>
      )}

      {rival.ai_strategy && (
        <section className="rival-card__section">
          <h3>AI strategy</h3>
          <p>{rival.ai_strategy}</p>
        </section>
      )}

      {rival.website && (
        <a
          className="rival-card__link"
          href={rival.website}
          target="_blank"
          rel="noopener noreferrer"
        >
          Visit website ↗
        </a>
      )}
    </aside>
  )
}
