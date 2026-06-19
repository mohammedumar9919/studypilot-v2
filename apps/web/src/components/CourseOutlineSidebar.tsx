import { useEffect, useState } from 'react'

import { useCourseOutline } from '../hooks/useCourseOutline'
import type { OutlineSection, OutlineSource, OutlineUnit } from '../types'
import {
  formatOutlineSectionLabel,
  formatOutlineUnitLabel,
  outlineChapterRollupNotice,
  outlineQualityBadge,
  outlineSourceNotice,
  outlineSourceNoticeClass,
  shouldEmphasizeOutlineRecovery,
  shouldShowOutlineConfirm,
  unitDefaultOpen,
} from '../utils/courseLabels'
import { dismissOutlineConfirm, isOutlineConfirmDismissed } from '../utils/outlineConfirmStorage'
import { OutlineConfirmPanel, OutlineManageActions } from './OutlineManageActions'

interface CourseOutlineSidebarProps {
  courseId: string
  refreshToken?: number
  outlineConfirmToken?: number
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
  outlineConfirmToken = 0,
  onSectionSelect,
  onOutlineState,
}: CourseOutlineSidebarProps) {
  const { data, loading, error, notFound, reload } = useCourseOutline(courseId, refreshToken)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [showConfirmPanel, setShowConfirmPanel] = useState(false)

  useEffect(() => {
    if (loading) return
    onOutlineState?.({
      loaded: true,
      notFound,
      hasData: Boolean(data),
    })
  }, [data, loading, notFound, onOutlineState])

  useEffect(() => {
    setShowConfirmPanel(false)
  }, [courseId])

  useEffect(() => {
    if (loading || !data) return
    if (data.outline_quality === 'high') {
      setShowConfirmPanel(false)
      return
    }
    if (!outlineConfirmToken) return
    if (!shouldShowOutlineConfirm(data.outline_quality, data.outline_source)) return
    if (isOutlineConfirmDismissed(courseId)) return
    setShowConfirmPanel(true)
  }, [data, loading, courseId, outlineConfirmToken])

  const handleSelect = (title: string) => {
    onSectionSelect(title)
    setMobileOpen(false)
  }

  const handleConfirmDismiss = () => {
    dismissOutlineConfirm(courseId)
    setShowConfirmPanel(false)
  }

  const handleOutlineActionSuccess = () => {
    reload()
  }

  const sourceNotice = data ? outlineSourceNotice(data.outline_source) : null
  const sourceNoticeClass = data
    ? outlineSourceNoticeClass(data.outline_source, data.outline_granularity, data.outline_quality)
    : 'outline-source-notice'
  const chapterNotice = data
    ? outlineChapterRollupNotice(data.units, data.outline_granularity)
    : null
  const qualityBadge = data ? outlineQualityBadge(data.outline_quality, data.outline_source) : null
  const emphasizeRecovery = data
    ? shouldEmphasizeOutlineRecovery(
        data.outline_granularity,
        data.outline_quality,
        data.outline_source,
      )
    : false

  return (
    <section className="panel course-outline-panel" aria-live="polite">
      <div className="course-outline-header">
        <div>
          <h2>Course outline</h2>
          <p className="panel-intro">Browse units before you search — click a section to prefill your question.</p>
          {qualityBadge && (
            <span className={qualityBadge.className} role="status">
              {qualityBadge.label}
            </span>
          )}
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
            {showConfirmPanel && (
              <OutlineConfirmPanel
                courseId={courseId}
                units={data.units}
                outlineSource={data.outline_source}
                onDismiss={handleConfirmDismiss}
                onSuccess={handleOutlineActionSuccess}
              />
            )}

            {sourceNotice && (
              <p className={sourceNoticeClass} role="status">
                {sourceNotice}
              </p>
            )}

            {chapterNotice && (
              <p className="outline-chapter-notice" role="status">
                {chapterNotice}
              </p>
            )}

            {!showConfirmPanel && (
              <OutlineManageActions
                courseId={courseId}
                outlineSource={data.outline_source}
                outlineQuality={data.outline_quality}
                prominent={emphasizeRecovery}
                onSuccess={handleOutlineActionSuccess}
              />
            )}

            <p className="course-outline-meta muted">
              {data.document} · {data.page_count} pages
            </p>

            <nav className="course-outline-tree" aria-label="Course table of contents">
              {data.front_matter && (
                <OutlineEntryButton
                  label={data.front_matter.title}
                  pageRange={formatPageRange(data.front_matter.page_start, data.front_matter.page_end)}
                  onSelect={() => handleSelect(data.front_matter!.title)}
                />
              )}

              {data.units.map((unit, unitIndex) => (
                <UnitGroup
                  key={unit.id}
                  unit={unit}
                  outlineSource={data.outline_source}
                  defaultOpen={unitDefaultOpen(
                    unit,
                    unitIndex,
                    data.units.length,
                    data.outline_source,
                  )}
                  onSectionSelect={handleSelect}
                />
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
  outlineSource,
  defaultOpen,
  onSectionSelect,
}: {
  unit: OutlineUnit
  outlineSource?: OutlineSource
  defaultOpen: boolean
  onSectionSelect: (title: string) => void
}) {
  return (
    <details className="outline-unit" open={defaultOpen}>
      <summary className="outline-unit-summary">
        <span className="outline-unit-label">{formatOutlineUnitLabel(unit, outlineSource)}</span>
        <span className="outline-unit-pages">{formatPageRange(unit.page_start, unit.page_end)}</span>
      </summary>

      <ul className="outline-section-list">
        {unit.sections.map((section) => (
          <li key={`${unit.id}-${section.title}-${section.page_start}`}>
            <SectionButton
              unit={unit}
              section={section}
              outlineSource={outlineSource}
              onSelect={onSectionSelect}
            />
          </li>
        ))}
      </ul>
    </details>
  )
}

function SectionButton({
  unit,
  section,
  outlineSource,
  onSelect,
}: {
  unit: OutlineUnit
  section: OutlineSection
  outlineSource?: OutlineSource
  onSelect: (title: string) => void
}) {
  return (
    <button
      type="button"
      className="outline-section-btn"
      onClick={() => onSelect(section.title)}
    >
      <span className="outline-section-label">
        {formatOutlineSectionLabel(unit, section, outlineSource)}
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
