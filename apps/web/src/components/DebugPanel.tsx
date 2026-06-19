import type { QueryResponse } from '../types'

interface DebugPanelProps {
  result: QueryResponse
}

export function DebugPanel({ result }: DebugPanelProps) {
  const { rerank_scores, retrieval_debug } = result
  const chunks = retrieval_debug?.chunks ?? []
  const pages = retrieval_debug?.pages ?? []
  const filenames = retrieval_debug?.filenames ?? []
  const refusalReason = retrieval_debug?.refusal_reason
  const topRerankScore = retrieval_debug?.top_rerank_score

  if (!retrieval_debug && rerank_scores.length === 0) {
    return (
      <section className="panel debug-panel">
        <h2>Debug</h2>
        <p className="muted">Enable debug mode before submitting to see retrieval details.</p>
      </section>
    )
  }

  return (
    <section className="panel debug-panel">
      <h2>Debug</h2>

      <div className="debug-section">
        <h3>Rerank scores</h3>
        {rerank_scores.length === 0 ? (
          <p className="muted">None</p>
        ) : (
          <ul className="score-list">
            {rerank_scores.map((score, index) => (
              <li key={index}>
                #{index + 1}: {score.toFixed(4)}
              </li>
            ))}
          </ul>
        )}
      </div>

      {retrieval_debug && (
        <>
          {refusalReason && chunks.length === 0 && (
            <div className="debug-section">
              <h3>Refusal summary</h3>
              <p className="muted">
                No chunks retrieved — {refusalReason}
                {typeof topRerankScore === 'number' && (
                  <> (top rerank score: {topRerankScore.toFixed(4)})</>
                )}
              </p>
            </div>
          )}

          <div className="debug-section">
            <h3>Retrieval summary</h3>
            <dl className="debug-dl">
              <div>
                <dt>Chunks</dt>
                <dd>{retrieval_debug.chunk_count ?? chunks.length}</dd>
              </div>
              <div>
                <dt>Pages (0-based)</dt>
                <dd>{pages.join(', ') || '—'}</dd>
              </div>
              <div>
                <dt>Filenames</dt>
                <dd>{[...new Set(filenames)].join(', ') || '—'}</dd>
              </div>
            </dl>
          </div>

          <div className="debug-section">
            <h3>Chunk details</h3>
            <div className="debug-table-wrap">
              <table className="debug-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Page</th>
                    <th>Filename</th>
                    <th>Rerank</th>
                    <th>Chunk ID</th>
                  </tr>
                </thead>
                <tbody>
                  {chunks.map((chunk, index) => (
                    <tr key={chunk.chunk_id}>
                      <td>{index + 1}</td>
                      <td>{chunk.page}</td>
                      <td>{chunk.filename}</td>
                      <td>
                        {typeof chunk.rerank_score === 'number' ? chunk.rerank_score.toFixed(4) : '—'}
                      </td>
                      <td className="mono">{chunk.chunk_id.slice(0, 8)}…</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </section>
  )
}
