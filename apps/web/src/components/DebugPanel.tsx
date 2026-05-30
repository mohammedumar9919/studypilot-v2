import type { QueryResponse } from '../types'

interface DebugPanelProps {
  result: QueryResponse
}

export function DebugPanel({ result }: DebugPanelProps) {
  const { rerank_scores, retrieval_debug } = result

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
          <div className="debug-section">
            <h3>Retrieval summary</h3>
            <dl className="debug-dl">
              <div>
                <dt>Chunks</dt>
                <dd>{retrieval_debug.chunk_count}</dd>
              </div>
              <div>
                <dt>Pages (0-based)</dt>
                <dd>{retrieval_debug.pages.join(', ') || '—'}</dd>
              </div>
              <div>
                <dt>Filenames</dt>
                <dd>{[...new Set(retrieval_debug.filenames)].join(', ') || '—'}</dd>
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
                  {retrieval_debug.chunks.map((chunk, index) => (
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
