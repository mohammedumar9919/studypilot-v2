interface EmptyCourseStateProps {
  compact?: boolean
}

export function EmptyCourseState({ compact = false }: EmptyCourseStateProps) {
  return (
    <section className={`panel empty-course-state glass-panel ${compact ? 'is-compact' : ''}`}>
      <div className="empty-course-icon" aria-hidden="true">
        ↑
      </div>
      <h2>Upload your notes to get started</h2>
      <p className="panel-intro">
        Add a course PDF above — StudyPilot indexes it locally, then you can ask questions with
        page citations.
      </p>
      <ul className="empty-course-steps">
        <li>Upload a PDF (notes, textbook, or syllabus)</li>
        <li>Wait for honest indexing (~30–60s)</li>
        <li>Ask a question and review cited sources</li>
      </ul>
    </section>
  )
}
