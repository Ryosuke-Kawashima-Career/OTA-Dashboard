import { useMemo } from 'react'

import { useRivalStore } from '../stores/rivalStore'

export function RivalCategoryFilter() {
  const rivals = useRivalStore((s) => s.rivals)
  const activeCategories = useRivalStore((s) => s.activeCategories)
  const toggleCategory = useRivalStore((s) => s.toggleCategory)
  const resetCategories = useRivalStore((s) => s.resetCategories)

  const categories = useMemo(() => {
    const set = new Set<string>()
    for (const r of rivals) {
      for (const c of r.categories) set.add(c)
    }
    return Array.from(set).sort()
  }, [rivals])

  if (categories.length === 0) return null

  return (
    <div className="rival-filter" role="group" aria-label="Filter rivals by category">
      <span className="rival-filter__label">Categories</span>
      <div className="rival-filter__chips">
        {categories.map((category) => {
          const active = activeCategories.has(category)
          return (
            <button
              key={category}
              type="button"
              className={`rival-filter__chip ${active ? 'rival-filter__chip--active' : ''}`}
              aria-pressed={active}
              onClick={() => toggleCategory(category)}
            >
              {category}
            </button>
          )
        })}
        <button
          type="button"
          className="rival-filter__reset"
          onClick={resetCategories}
          aria-label="Reset category filter"
        >
          All
        </button>
      </div>
    </div>
  )
}
