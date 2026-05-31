import type { QueryStage } from '../types'

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
): number {
  if (uploadIndexing) return 0

  switch (stage) {
    case 'retrieving':
      return 1
    case 'generating':
      if (hasAnswer) return 3
      if (hasSources) return 2
      return 1
    case 'done':
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
}: StudyJourneyStripProps) {
  const active = activeStepIndex(stage, hasSources, hasAnswer, uploadIndexing)
  const isLoading = uploadIndexing || stage === 'retrieving' || stage === 'generating'

  return (
    <nav className="study-journey reveal-on-load" aria-label="Study journey">
      <ol className="study-journey-list">
        {STEPS.map((step, index) => {
          const isActive = index === active && (isLoading || stage === 'done')
          const isComplete = index < active || (stage === 'done' && index <= active)

          return (
            <li
              key={step.id}
              className={[
                'study-journey-step',
                isActive ? 'is-active' : '',
                isComplete ? 'is-complete' : '',
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
