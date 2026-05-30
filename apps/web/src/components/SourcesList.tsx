import type { RetrievalDebugChunk, Source } from '../types'

interface SourcesListProps {
  sources: Source[]
  debugChunks?: RetrievalDebugChunk[] | null
}

export function SourcesList({ sources, debugChunks }: SourcesListProps) {
  if (sources.length === 0) {
    return <p className="muted">No sources returned.</p>
  }

  return (
    <ol className="sources-list">
      {sources.map((source, index) => {
        const matchedChunk = findMatchingChunk(source, debugChunks)
        return (
          <li key={`${source.document_id}-${source.page}-${index}`} className="source-item">
            <div className="source-card-header">
              <div className="source-card-meta">
                <span className="source-filename">{source.filename}</span>
                <span className="source-page-badge">p.{source.page + 1}</span>
              </div>
              {(matchedChunk?.section_title || matchedChunk?.toc_path) && (
                <div className="source-outline">
                  {matchedChunk.section_title && (
                    <span className="source-section">{matchedChunk.section_title}</span>
                  )}
                  {matchedChunk.toc_path && (
                    <span className="source-toc-path">{matchedChunk.toc_path}</span>
                  )}
                </div>
              )}
            </div>
            <p className="source-excerpt">{source.excerpt}</p>
          </li>
        )
      })}
    </ol>
  )
}

function findMatchingChunk(
  source: Source,
  debugChunks: RetrievalDebugChunk[] | null | undefined,
): RetrievalDebugChunk | null {
  if (!debugChunks?.length) return null
  return (
    debugChunks.find(
      (chunk) => chunk.filename === source.filename && chunk.page === source.page,
    ) ?? null
  )
}
