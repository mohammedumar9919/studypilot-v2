import type { QueryStage } from '../types'

interface ProgressIndicatorProps {
  stage: QueryStage
  elapsedMs: number
}

function formatElapsed(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return minutes > 0
    ? `${minutes}:${seconds.toString().padStart(2, '0')}`
    : `${seconds}s`
}

function stageLabel(stage: QueryStage): string | null {
  switch (stage) {
    case 'retrieving':
      return 'Finding sources…'
    case 'generating':
      return 'Writing answer…'
    default:
      return null
  }
}

export function ProgressIndicator({ stage, elapsedMs }: ProgressIndicatorProps) {
  const label = stageLabel(stage)
  if (!label) return null

  return (
    <div className="progress-indicator" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span className="progress-label">{label}</span>
      <span className="progress-elapsed">{formatElapsed(elapsedMs)}</span>
    </div>
  )
}
