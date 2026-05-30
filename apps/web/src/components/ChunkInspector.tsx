import { GOLDEN_MISSES } from '../constants/goldenMisses'
import type { GoldenMissHint, QueryResponse } from '../types'
import { evaluatePageMatch } from '../utils/pageMatch'

interface ChunkInspectorProps {
  selectedHint: GoldenMissHint | null
  onSelectHint: (hint: GoldenMissHint | null) => void
  onLoadQuestion: (question: string) => void
  result: QueryResponse | null
  debugEnabled: boolean
  selectedChunkId: string | null
  onSelectChunkId: (chunkId: string | null) => void
}

export function ChunkInspector({
  selectedHint,
  onSelectHint,
  onLoadQuestion,
  result,
  debugEnabled,
  selectedChunkId,
  onSelectChunkId,
}: ChunkInspectorProps) {
  const retrievedPages = result?.retrieval_debug?.pages ?? []
  const pageMatch =
    selectedHint && retrievedPages.length > 0
      ? evaluatePageMatch(retrievedPages, selectedHint.expectedPages)
      : null

  const selectedChunk =
    selectedChunkId && result?.retrieval_debug?.chunks
      ? result.retrieval_debug.chunks.find((chunk) => chunk.chunk_id === selectedChunkId) ?? null
      : null

  return (
    <section className="panel chunk-inspector">
      <h2>Chunk inspector</h2>
      <p className="panel-intro">
        {GOLDEN_MISSES.length > 0
          ? `Replay golden-set misses (${GOLDEN_MISSES.length} loaded). Compare retrieved pages against expected pages (±1 tolerance).`
          : 'Golden set at 100% precision@5 — no remaining misses. Use developer mode to inspect retrieval chunks.'}
      </p>

      {GOLDEN_MISSES.length > 0 ? (
        <label className="field">
          <span>Golden miss ID</span>
          <select
            value={selectedHint?.id ?? ''}
            onChange={(event) => {
              const id = event.target.value
              if (!id) {
                onSelectHint(null)
                return
              }
              const hint = GOLDEN_MISSES.find((item) => item.id === id) ?? null
              onSelectHint(hint)
              if (hint) onLoadQuestion(hint.question)
            }}
          >
            <option value="">— Select a miss —</option>
            {GOLDEN_MISSES.map((hint) => (
              <option key={hint.id} value={hint.id}>
                {hint.id} (Unit {hint.unit}, p.
                {hint.expectedPages.map((p) => p + 1).join(', p.')})
              </option>
            ))}
          </select>
        </label>
      ) : (
        <p className="muted">No golden misses in the replay list.</p>
      )}

      {selectedHint && (
        <div className="hint-card">
          <h3>{selectedHint.id}</h3>
          <p className="hint-question">{selectedHint.question}</p>
          <dl className="hint-dl">
            <div>
              <dt>Expected doc</dt>
              <dd>{selectedHint.expectedDoc}</dd>
            </div>
            <div>
              <dt>Expected pages (0-based)</dt>
              <dd>{selectedHint.expectedPages.join(', ')}</dd>
            </div>
            <div>
              <dt>Display pages</dt>
              <dd>{selectedHint.expectedPages.map((p) => p + 1).join(', ')}</dd>
            </div>
          </dl>
        </div>
      )}

      {!debugEnabled && (
        <p className="muted warning">Enable debug mode and submit to inspect retrieved chunks.</p>
      )}

      {result?.retrieval_debug && selectedHint && (
        <div className="comparison">
          <h3>Page comparison</h3>
          <dl className="comparison-dl">
            <div>
              <dt>Retrieved (0-based)</dt>
              <dd>{retrievedPages.join(', ') || '—'}</dd>
            </div>
            <div>
              <dt>Match (±1 page)</dt>
              <dd className={pageMatch?.hit ? 'match-yes' : 'match-no'}>
                {pageMatch?.hit ? 'HIT' : 'MISS'}
              </dd>
            </div>
            {pageMatch && pageMatch.matchedPages.length > 0 && (
              <div>
                <dt>Matched retrieved pages</dt>
                <dd>{pageMatch.matchedPages.join(', ')}</dd>
              </div>
            )}
            {pageMatch && pageMatch.missedExpected.length > 0 && (
              <div>
                <dt>Uncovered expected</dt>
                <dd>{pageMatch.missedExpected.join(', ')}</dd>
              </div>
            )}
          </dl>

          <div className="debug-table-wrap">
            <table className="debug-table">
              <thead>
                <tr>
                  <th>Page</th>
                  <th>Expected?</th>
                  <th>Rerank</th>
                  <th>Filename</th>
                </tr>
              </thead>
              <tbody>
                {result.retrieval_debug.chunks.map((chunk) => {
                  const expected = pageHitsChunk(chunk.page, selectedHint.expectedPages)
                  return (
                    <tr
                      key={chunk.chunk_id}
                      className={[
                        expected ? 'row-hit' : 'row-miss',
                        chunk.chunk_id === selectedChunkId ? 'row-selected' : '',
                      ]
                        .filter(Boolean)
                        .join(' ')}
                      onClick={() => onSelectChunkId(chunk.chunk_id)}
                      role="button"
                      tabIndex={0}
                    >
                      <td>{chunk.page}</td>
                      <td>{expected ? '✓' : '—'}</td>
                      <td>
                        {typeof chunk.rerank_score === 'number' ? chunk.rerank_score.toFixed(4) : '—'}
                      </td>
                      <td>{chunk.filename}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {result?.retrieval_debug && debugEnabled && (
        <div className="retrieval-chunks">
          <h3>Retrieved chunks (latest query)</h3>

          {selectedChunk ? (
            <div className="chunk-card">
              <div className="chunk-card-title">
                <span className="chunk-card-id mono">{selectedChunk.chunk_id.slice(0, 8)}…</span>
                <span className="chunk-card-meta">
                  p.{selectedChunk.page + 1} · {selectedChunk.filename}
                </span>
              </div>
              <dl className="chunk-dl">
                <div>
                  <dt>Unit</dt>
                  <dd>{normalizeLabel(selectedChunk.unit)}</dd>
                </div>
                <div>
                  <dt>TOC path</dt>
                  <dd>{normalizeLabel(selectedChunk.toc_path)}</dd>
                </div>
                <div>
                  <dt>Section title</dt>
                  <dd>{normalizeLabel(selectedChunk.section_title)}</dd>
                </div>
                <div>
                  <dt>Rerank</dt>
                  <dd>
                    {typeof selectedChunk.rerank_score === 'number'
                      ? selectedChunk.rerank_score.toFixed(4)
                      : '—'}
                  </dd>
                </div>
              </dl>
              {getChunkSnippet(selectedChunk) && (
                <p className="chunk-snippet">{getChunkSnippet(selectedChunk)}</p>
              )}
            </div>
          ) : (
            <p className="muted">Select a chunk from the TOC browser to inspect details.</p>
          )}

          <div className="debug-table-wrap">
            <table className="debug-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Page</th>
                  <th>Unit</th>
                  <th>TOC path</th>
                  <th>Section</th>
                  <th>Rerank</th>
                </tr>
              </thead>
              <tbody>
                {result.retrieval_debug.chunks.map((chunk, index) => {
                  const selected = chunk.chunk_id === selectedChunkId
                  return (
                    <tr
                      key={chunk.chunk_id}
                      className={selected ? 'row-selected' : undefined}
                      onClick={() => onSelectChunkId(chunk.chunk_id)}
                      role="button"
                      tabIndex={0}
                    >
                      <td>{index + 1}</td>
                      <td>{chunk.page + 1}</td>
                      <td>{normalizeLabel(chunk.unit)}</td>
                      <td>{normalizeLabel(chunk.toc_path)}</td>
                      <td>{normalizeLabel(chunk.section_title)}</td>
                      <td>{typeof chunk.rerank_score === 'number' ? chunk.rerank_score.toFixed(4) : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {result && !result.retrieval_debug && debugEnabled && (
        <p className="muted">No retrieval debug returned (refusal or empty retrieval).</p>
      )}
    </section>
  )
}

function pageHitsChunk(page: number, expectedPages: number[]): boolean {
  return expectedPages.some((expected) => Math.abs(page - expected) <= 1)
}

function normalizeLabel(value: string | null | undefined): string {
  const trimmed = (value ?? '').trim()
  return trimmed || '—'
}

function getChunkSnippet(chunk: { excerpt?: string | null; snippet?: string | null; text?: string | null }) {
  const raw = chunk.excerpt ?? chunk.snippet ?? chunk.text ?? ''
  const trimmed = raw?.trim() ?? ''
  if (!trimmed) return ''
  return trimmed.length > 280 ? `${trimmed.slice(0, 280)}…` : trimmed
}
