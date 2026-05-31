import { useEffect, useState } from 'react'

import { useCourseOutline } from '../hooks/useCourseOutline'
import type { OutlineSection, OutlineUnit } from '../types'

interface CourseOutlineSidebarProps {
  courseId: string
  refreshToken?: number
  onSectionSelect: (sectionTitle: string) => void
  onOutlineState?: (state: { loaded: boolean; notFound: boolean; hasData: boolean }) => void
}

function formatPageRange(pageStart: number, pageEnd: number): string {
  const start = pageStart + 1
  const end = pageEnd + 1
  return start === end ? `p.${start}` : `pp.${start}–${end}`
}

export function CourseOutlineSidebar({
  courseId,
  refreshToken = 0,
  onSectionSelect,
  onOutlineState,
}: CourseOutlineSidebarProps) {
  const { data, loading, error, notFound, reload } = useCourseOutline(courseId, refreshToken)
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    if (loading) return
    onOutlineState?.({
      loaded: true,
      notFound,
      hasData: Boolean(data),
    })
  }, [data, loading, notFound, onOutlineState])

  const handleSelect = (title: string) => {
    onSectionSelect(title)
    setMobileOpen(false)
  }

  return (
    <section className="panel course-outline-panel" aria-live="polite">
      <div className="course-outline-header">
        <div>
          <h2>Course outline</h2>
          <p className="panel-intro">Browse units before you search — click a section to prefill your question.</p>
        </div>
        {!loading && (
          <button type="button" className="text-btn" onClick={reload}>
            Refresh
          </button>
        )}
      </div>

      <button
        type="button"
        className="outline-mobile-toggle"
        aria-expanded={mobileOpen}
        onClick={() => setMobileOpen((open) => !open)}
      >
        {mobileOpen ? 'Hide outline' : 'Show outline'}
      </button>

      <div className={`course-outline-body ${mobileOpen ? 'is-open' : ''}`}>
        {loading && (
          <div className="course-outline-loading">
            <span className="spinner" aria-hidden="true" />
            Loading outline…
          </div>
        )}

        {!loading && error && (
          <div className={`course-outline-alert ${notFound ? 'alert-muted' : 'alert-error'}`} role="alert">
            <p>{error}</p>
            {!notFound && (
              <button type="button" className="text-btn" onClick={reload}>
                Retry
              </button>
            )}
          </div>
        )}

        {!loading && data && (
          <>
            <p className="course-outline-meta muted">
              {data.document} · {data.page_count} pages
            </p>

            <nav className="course-outline-tree" aria-label="Course table of contents">
              {data.front_matter && (
                <OutlineEntryButton
                  label={data.front_matter.title}
                  pageRange={formatPageRange(data.front_matter.page_start, data.front_matter.page_end)}
                  onSelect={() => handleSelect(data.front_matter.title)}
                />
              )}

              {data.units.map((unit) => (
                <UnitGroup key={unit.id} unit={unit} onSectionSelect={handleSelect} />
              ))}
            </nav>
          </>
        )}
      </div>
    </section>
  )
}

function UnitGroup({
  unit,
  onSectionSelect,
}: {
  unit: OutlineUnit
  onSectionSelect: (title: string) => void
}) {
  return (
    <details className="outline-unit" open={unit.id === '1'}>
      <summary className="outline-unit-summary">
        <span className="outline-unit-label">
          Unit {unit.id}: {unit.title}
        </span>
        <span className="outline-unit-pages">{formatPageRange(unit.page_start, unit.page_end)}</span>
      </summary>

      <ul className="outline-section-list">
        {unit.sections.map((section) => (
          <li key={`${unit.id}-${section.title}`}>
            <SectionButton unit={unit} section={section} onSelect={onSectionSelect} />
          </li>
        ))}
      </ul>
    </details>
  )
}

function SectionButton({
  unit,
  section,
  onSelect,
}: {
  unit: OutlineUnit
  section: OutlineSection
  onSelect: (title: string) => void
}) {
  return (
    <button
      type="button"
      className="outline-section-btn"
      onClick={() => onSelect(section.title)}
    >
      <span className="outline-section-label">
        Unit {unit.id} &gt; {section.title}
      </span>
      <span className="outline-section-pages">{formatPageRange(section.page_start, section.page_end)}</span>
    </button>
  )
}

function OutlineEntryButton({
  label,
  pageRange,
  onSelect,
}: {
  label: string
  pageRange: string
  onSelect: () => void
}) {
  return (
    <button type="button" className="outline-section-btn outline-front-matter" onClick={onSelect}>
      <span className="outline-section-label">{label}</span>
      <span className="outline-section-pages">{pageRange}</span>
    </button>
  )
}
