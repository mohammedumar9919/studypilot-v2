import { isCourseMapPromoteExtractionFailure } from '../api/courseMapClient'
import type {
  CourseMapEligibilityResponse,
  ExamHeatmapSource,
  QueryPreset,
  StructureMode,
} from '../types'
import { CourseMapPromotionPanel } from './CourseMapPromotionPanel'
import { CourseOutlineSidebar } from './CourseOutlineSidebar'
import { ExamAnalyticsPanel } from './ExamAnalyticsPanel'

interface CourseMapTabPanelProps {
  courseId: string
  structureMode: StructureMode
  outlineAvailable: boolean
  refreshToken: number
  outlineConfirmToken: number
  queryPreset: QueryPreset
  heatmapSource: ExamHeatmapSource | undefined
  onSectionSelect: (sectionTitle: string) => void
  onSelectExamPreset: () => void
  onConceptsLoaded?: (labels: string[]) => void
  onOutlineState?: (state: { loaded: boolean; notFound: boolean; hasData: boolean }) => void
  eligibility: CourseMapEligibilityResponse | null
  eligibilityLoading: boolean
  eligibilityError: string | null
  promoting: boolean
  promoteError: string | null
  onPromote: () => void
  onReloadEligibility: () => void
  rebuilding: boolean
  rebuildError: string | null
  onRebuildOutline: () => void
}

export function CourseMapTabPanel({
  courseId,
  structureMode,
  outlineAvailable,
  refreshToken,
  outlineConfirmToken,
  queryPreset,
  heatmapSource,
  onSectionSelect,
  onSelectExamPreset,
  onConceptsLoaded,
  onOutlineState,
  eligibility,
  eligibilityLoading,
  eligibilityError,
  promoting,
  promoteError,
  onPromote,
  onReloadEligibility,
  rebuilding,
  rebuildError,
  onRebuildOutline,
}: CourseMapTabPanelProps) {
  const showPromoteSecondary =
    outlineAvailable && structureMode !== 'mapped' && eligibility?.eligible === true

  const showRebuildPrimary = !outlineAvailable && structureMode === 'mapped'
  const showPromotePrimary = !outlineAvailable && structureMode !== 'mapped'

  const extractionFailure =
    isCourseMapPromoteExtractionFailure(promoteError) ||
    isCourseMapPromoteExtractionFailure(rebuildError)

  if (outlineAvailable) {
    return (
      <>
        <CourseOutlineSidebar
          courseId={courseId}
          refreshToken={refreshToken}
          outlineConfirmToken={outlineConfirmToken}
          onSectionSelect={onSectionSelect}
          onOutlineState={onOutlineState}
        />

        <ExamAnalyticsPanel
          courseId={courseId}
          refreshToken={refreshToken}
          queryPreset={queryPreset}
          heatmapSource={heatmapSource}
          onSelectExamPreset={onSelectExamPreset}
          onConceptsLoaded={onConceptsLoaded}
        />

        {showPromoteSecondary && (
          <section className="panel course-map-secondary-panel">
            <h3 className="course-map-secondary-title">Upgrade to full Course Map</h3>
            <p className="muted panel-intro">
              Promote when your syllabus outline is ready — keeps Sources and Topics tabs available.
            </p>
            <CourseMapPromotionPanel
              courseId={courseId}
              eligibility={eligibility}
              loading={eligibilityLoading}
              error={eligibilityError}
              promoting={promoting}
              promoteError={promoteError}
              onPromote={onPromote}
              onReload={onReloadEligibility}
            />
          </section>
        )}
      </>
    )
  }

  return (
    <section className="panel course-map-tab-panel" aria-live="polite">
      <div className="sources-panel-header">
        <div>
          <div className="sources-panel-title-row">
            <h2>Course map</h2>
          </div>
          <p className="panel-intro">
            Unit sidebar and exam heatmap — extract or promote from your syllabus outline.
          </p>
        </div>
      </div>

      {showRebuildPrimary && (
        <div className="course-map-rebuild-panel">
          <p>No unit outline stored yet — re-extract from your syllabus PDF.</p>
          <button
            type="button"
            className="submit-btn course-map-rebuild-btn"
            disabled={rebuilding}
            onClick={onRebuildOutline}
          >
            {rebuilding ? 'Extracting…' : 'Extract from syllabus'}
          </button>
          {rebuildError && (
            <div className="sources-panel-alert alert-error" role="alert">
              <p>{rebuildError}</p>
            </div>
          )}
        </div>
      )}

      {showPromotePrimary && (
        <CourseMapPromotionPanel
          courseId={courseId}
          eligibility={eligibility}
          loading={eligibilityLoading}
          error={eligibilityError}
          promoting={promoting}
          promoteError={promoteError}
          onPromote={onPromote}
          onReload={onReloadEligibility}
        />
      )}

      {extractionFailure && showRebuildPrimary && (
        <p className="muted">
          Or upload a JSON outline using the upload panel in the promotion flow above.
        </p>
      )}
    </section>
  )
}
