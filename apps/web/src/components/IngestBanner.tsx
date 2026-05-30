export function IngestBanner() {
  return (
    <aside className="ingest-banner" role="status">
      <strong>Corpus ingest:</strong> Upload via{' '}
      <code>scripts/ingest_ppl.ps1</code> until upload API exists.
    </aside>
  )
}
