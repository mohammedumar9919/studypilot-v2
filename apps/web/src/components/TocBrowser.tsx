import { useMemo, useState } from 'react'

import type { RetrievalDebugChunk } from '../types'

type TocBrowserChunk = RetrievalDebugChunk

interface TocBrowserProps {
  chunks: TocBrowserChunk[]
  selectedChunkId: string | null
  onSelectChunkId: (chunkId: string | null) => void
}

type TocPathGroup = {
  tocPathLabel: string
  chunks: TocBrowserChunk[]
}

type UnitGroup = {
  unitLabel: string
  tocGroups: TocPathGroup[]
}

const UNKNOWN_UNIT_LABEL = 'Front matter / Unknown'
const UNKNOWN_TOC_LABEL = 'Unknown'

export function TocBrowser({ chunks, selectedChunkId, onSelectChunkId }: TocBrowserProps) {
  const [unitFilter, setUnitFilter] = useState<string>('__all__')
  const [textFilter, setTextFilter] = useState('')

  const normalizedTextFilter = textFilter.trim().toLowerCase()

  const unitOptions = useMemo(() => {
    const units = new Set<string>()
    for (const chunk of chunks) {
      const label = normalizeUnit(chunk.unit)
      units.add(label)
    }
    return [__ALL_LABEL, ...Array.from(units).sort()]
  }, [chunks])

  const grouped = useMemo<UnitGroup[]>(() => {
    const byUnit = new Map<string, TocBrowserChunk[]>()
    for (const chunk of chunks) {
      const unitLabel = normalizeUnit(chunk.unit)
      const list = byUnit.get(unitLabel)
      if (list) list.push(chunk)
      else byUnit.set(unitLabel, [chunk])
    }

    const unitGroups: UnitGroup[] = []
    const unitLabels = Array.from(byUnit.keys()).sort(unitLabelSort)

    for (const unitLabel of unitLabels) {
      if (unitFilter !== '__all__' && unitLabel !== unitFilter) continue

      const unitChunks = byUnit.get(unitLabel) ?? []
      const byTocPath = new Map<string, TocBrowserChunk[]>()

      for (const chunk of unitChunks) {
        const tocLabel = normalizeTocPath(chunk.toc_path)
        if (normalizedTextFilter) {
          const haystack = `${tocLabel} ${chunk.section_title ?? ''}`.toLowerCase()
          if (!haystack.includes(normalizedTextFilter)) continue
        }
        const list = byTocPath.get(tocLabel)
        if (list) list.push(chunk)
        else byTocPath.set(tocLabel, [chunk])
      }

      const tocGroups: TocPathGroup[] = Array.from(byTocPath.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([tocPathLabel, groupChunks]) => ({
          tocPathLabel,
          chunks: groupChunks.sort(chunkSort),
        }))

      unitGroups.push({ unitLabel, tocGroups })
    }

    return unitGroups
  }, [chunks, normalizedTextFilter, unitFilter])

  const empty = chunks.length === 0

  return (
    <section className="panel toc-browser">
      <h2>TOC browser</h2>
      <p className="panel-intro">
        Browse retrieved chunks grouped by unit and outline path. Click a chunk to highlight
        it in the inspector.
      </p>

      <div className="toc-filters">
        <label className="field toc-filter">
          <span>Unit</span>
          <select value={unitFilter} onChange={(e) => setUnitFilter(e.target.value)}>
            {unitOptions.map((label) => (
              <option key={label} value={label === __ALL_LABEL ? '__all__' : label}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className="field toc-filter">
          <span>Filter</span>
          <input
            value={textFilter}
            onChange={(e) => setTextFilter(e.target.value)}
            placeholder="Search toc_path / section_title"
          />
        </label>
      </div>

      {empty ? (
        <p className="muted">No retrieved chunks yet. Submit with debug enabled.</p>
      ) : grouped.length === 0 ? (
        <p className="muted">No chunks match the current filters.</p>
      ) : (
        <div className="toc-tree">
          {grouped.map((unitGroup) => (
            <details key={unitGroup.unitLabel} className="toc-unit" open>
              <summary className="toc-unit-summary">
                <span className="toc-unit-label">{unitGroup.unitLabel}</span>
                <span className="toc-unit-count">{countUnitChunks(unitGroup)} chunks</span>
              </summary>

              <div className="toc-unit-body">
                {unitGroup.tocGroups.map((tocGroup) => (
                  <details key={tocGroup.tocPathLabel} className="toc-path" open>
                    <summary className="toc-path-summary">
                      <span className="toc-path-label">{tocGroup.tocPathLabel}</span>
                      <span className="toc-path-count">{tocGroup.chunks.length}</span>
                    </summary>

                    <ul className="toc-chunk-list">
                      {tocGroup.chunks.map((chunk) => {
                        const selected = chunk.chunk_id === selectedChunkId
                        return (
                          <li key={chunk.chunk_id} className="toc-chunk-item">
                            <button
                              type="button"
                              className={selected ? 'toc-chunk-btn selected' : 'toc-chunk-btn'}
                              onClick={() => onSelectChunkId(chunk.chunk_id)}
                            >
                              <div className="toc-chunk-title">
                                <span className="toc-chunk-page">p.{chunk.page + 1}</span>
                                <span className="toc-chunk-section">
                                  {chunk.section_title ?? '—'}
                                </span>
                                <span className="toc-chunk-score">
                                  {typeof chunk.rerank_score === 'number'
                                    ? chunk.rerank_score.toFixed(4)
                                    : '—'}
                                </span>
                              </div>
                              <div className="toc-chunk-snippet">{getChunkSnippet(chunk)}</div>
                            </button>
                          </li>
                        )
                      })}
                    </ul>
                  </details>
                ))}
              </div>
            </details>
          ))}
        </div>
      )}
    </section>
  )
}

const __ALL_LABEL = 'All units'

function normalizeUnit(unit: string | null | undefined): string {
  const value = (unit ?? '').trim()
  if (!value) return UNKNOWN_UNIT_LABEL
  // If backend already includes "Unit X", keep it; otherwise keep raw string.
  return value
}

function normalizeTocPath(tocPath: string | null | undefined): string {
  const value = (tocPath ?? '').trim()
  return value || UNKNOWN_TOC_LABEL
}

function unitLabelSort(a: string, b: string): number {
  if (a === UNKNOWN_UNIT_LABEL && b !== UNKNOWN_UNIT_LABEL) return 1
  if (b === UNKNOWN_UNIT_LABEL && a !== UNKNOWN_UNIT_LABEL) return -1
  return a.localeCompare(b)
}

function chunkSort(a: TocBrowserChunk, b: TocBrowserChunk): number {
  // Prefer higher rerank first; then page asc; then stable id.
  const aScore = typeof a.rerank_score === 'number' ? a.rerank_score : Number.NEGATIVE_INFINITY
  const bScore = typeof b.rerank_score === 'number' ? b.rerank_score : Number.NEGATIVE_INFINITY
  if (aScore !== bScore) return bScore - aScore
  if (a.page !== b.page) return a.page - b.page
  return a.chunk_id.localeCompare(b.chunk_id)
}

function getChunkSnippet(chunk: TocBrowserChunk): string {
  const raw = chunk.excerpt ?? chunk.snippet ?? chunk.text ?? ''
  const value = raw?.trim() ?? ''
  if (!value) return ''
  return value.length > 180 ? `${value.slice(0, 180)}…` : value
}

function countUnitChunks(unitGroup: UnitGroup): number {
  return unitGroup.tocGroups.reduce((sum, group) => sum + group.chunks.length, 0)
}

