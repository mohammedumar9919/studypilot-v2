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

function stageParts(stage: QueryStage): { prefix: string; accent: string; suffix: string } | null {
  switch (stage) {
    case 'retrieving':
      return { prefix: 'Finding ', accent: 'sources', suffix: '…' }
    case 'generating':
      return { prefix: 'Writing ', accent: 'answer', suffix: '…' }
    default:
      return null
  }
}

export function ProgressIndicator({ stage, elapsedMs }: ProgressIndicatorProps) {
  const parts = stageParts(stage)
  if (!parts) return null

  return (
    <div className="stage-pill progress-indicator" aria-live="polite">
      <span className="stage-pill-dot" aria-hidden="true" />
      <span className="stage-pill-label">
        {parts.prefix}
        <span className="gradient-accent">{parts.accent}</span>
        {parts.suffix}
      </span>
      <span className="progress-elapsed">{formatElapsed(elapsedMs)}</span>
    </div>
  )
}
