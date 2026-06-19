import type { QueryPreset, QueryStage } from '../types'
import { isExamPreset } from '../constants/queryPresets'

const STEPS = [
  { id: 'start', label: 'Upload', number: '01' },
  { id: 'retrieve', label: 'Retrieve', number: '02' },
  { id: 'cite', label: 'Cite', number: '03' },
  { id: 'review', label: 'Review', number: '04' },
  { id: 'exam', label: 'Exam', number: '05' },
] as const

interface StudyJourneyStripProps {
  stage: QueryStage
  hasSources: boolean
  hasAnswer: boolean
  uploadIndexing?: boolean
  queryPreset?: QueryPreset
}

function isReviewPreset(preset: QueryPreset | undefined): boolean {
  return preset === 'summary' || preset === 'flashcards'
}

function stepLabel(index: number, baseLabel: string, uploadIndexing: boolean, stage: QueryStage): string {
  if (index !== 0) return baseLabel
  if (uploadIndexing) return 'Index'
  if (stage === 'retrieving' || stage === 'generating' || stage === 'done') return 'Ask'
  return 'Upload'
}

function activeStepIndex(
  stage: QueryStage,
  hasSources: boolean,
  hasAnswer: boolean,
  uploadIndexing: boolean,
  queryPreset?: QueryPreset,
): number {
  if (uploadIndexing) return 0

  const reviewPreset = isReviewPreset(queryPreset)
  const examPreset = isExamPreset(queryPreset)

  switch (stage) {
    case 'retrieving':
      return 1
    case 'generating':
      if (hasAnswer) return examPreset ? 4 : 3
      if (hasSources) return 2
      return 1
    case 'done':
      if (examPreset) return 4
      if (reviewPreset) return 3
      return 4
    case 'error':
      return 0
    default:
      return 0
  }
}

export function StudyJourneyStrip({
  stage,
  hasSources,
  hasAnswer,
  uploadIndexing = false,
  queryPreset = 'study',
}: StudyJourneyStripProps) {
  const active = activeStepIndex(stage, hasSources, hasAnswer, uploadIndexing, queryPreset)
  const isLoading = uploadIndexing || stage === 'retrieving' || stage === 'generating'
  const presetFocusReview = isReviewPreset(queryPreset) && stage === 'idle'
  const presetFocusExam = isExamPreset(queryPreset) && stage === 'idle'

  return (
    <nav className="study-journey reveal-on-load" aria-label="Study journey">
      <ol className="study-journey-list">
        {STEPS.map((step, index) => {
          const isActive = index === active && (isLoading || stage === 'done')
          const isComplete = index < active || (stage === 'done' && index <= active)
          const isPresetFocus =
            (presetFocusReview && index === 3) || (presetFocusExam && index === 4)

          return (
            <li
              key={step.id}
              className={[
                'study-journey-step',
                isActive ? 'is-active' : '',
                isComplete ? 'is-complete' : '',
                isPresetFocus ? 'is-preset-focus' : '',
              ]
                .filter(Boolean)
                .join(' ')}
            >
              <span className="study-journey-number">{step.number}</span>
              <span className="study-journey-label">
                {stepLabel(index, step.label, uploadIndexing, stage)}
              </span>
              {index < STEPS.length - 1 && (
                <span className="study-journey-arrow" aria-hidden="true">
                  →
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
