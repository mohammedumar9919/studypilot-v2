import type {
  OutlineGranularity,
  OutlineQuality,
  OutlineSource,
  OutlineSection,
  OutlineUnit,
  TopicFrequencyUnit,
} from '../types'

export function outlineQualityBadge(
  quality?: OutlineQuality,
  outlineSource?: OutlineSource,
): { label: string; className: string } | null {
  if (outlineSource === 'fixture' || !quality || quality === 'high') return null
  if (quality === 'medium') {
    return {
      label: 'Outline: review recommended',
      className: 'outline-quality-badge outline-quality-medium',
    }
  }
  return {
    label: 'Outline: review recommended',
    className: 'outline-quality-badge outline-quality-low',
  }
}

export function shouldShowOutlineConfirm(quality?: OutlineQuality, outlineSource?: OutlineSource): boolean {
  if (outlineSource === 'fixture') return false
  if (!quality || quality === 'high') return false
  return true
}

export function shouldEmphasizeOutlineRecovery(
  granularity?: OutlineGranularity,
  quality?: OutlineQuality,
  outlineSource?: OutlineSource,
): boolean {
  return (
    granularity === 'page_stub' ||
    quality === 'low' ||
    outlineSource === 'auto_stub'
  )
}

export function outlineSourceNoticeClass(
  outlineSource?: OutlineSource,
  granularity?: OutlineGranularity,
  quality?: OutlineQuality,
): string {
  const base = (() => {
    switch (outlineSource) {
      case 'extracted':
        return 'outline-source-notice outline-source-extracted'
      case 'uploaded':
        return 'outline-source-notice outline-source-uploaded'
      case 'auto_stub':
        return 'outline-source-notice outline-source-stub'
      default:
        return 'outline-source-notice'
    }
  })()

  if (shouldEmphasizeOutlineRecovery(granularity, quality, outlineSource)) {
    return `${base} outline-source-emphasis`
  }
  return base
}

export function unitDefaultOpen(
  unit: OutlineUnit,
  unitIndex: number,
  unitCount: number,
  outlineSource?: OutlineSource,
): boolean {
  if (outlineSource === 'fixture') return unit.id === '1'
  if (outlineSource === 'extracted' || outlineSource === 'uploaded') return unitIndex === 0
  return unitIndex === 0 || unitCount <= 3
}

export function outlineChapterRollupNotice(
  units: OutlineUnit[],
  granularity?: OutlineGranularity,
): string | null {
  const unitCount = units.length
  if (unitCount === 0) return null

  const totalSections = units.reduce((sum, unit) => sum + (unit.sections ?? []).length, 0)
  const showBanner =
    granularity === 'chapter' ||
    (unitCount >= 3 && unitCount <= 8 && totalSections > unitCount * 2)

  if (!showBanner) return null
  return `Showing ${unitCount} chapters — expand a unit for subtopics`
}

export function shouldDefaultShowSectionBreakdown(units: TopicFrequencyUnit[]): boolean {
  const unitsWithSections = units.filter((unit) => (unit.sections ?? []).length > 0)
  if (unitsWithSections.length === 0) return false
  return units.length <= 5 && unitsWithSections.length === units.length
}

export function topicFrequencyHasSectionDetail(units: TopicFrequencyUnit[]): boolean {
  return units.some((unit) => (unit.sections ?? []).length > 0)
}

export function canToggleSectionBreakdown(
  units: TopicFrequencyUnit[],
  totalQuestions: number,
): boolean {
  return topicFrequencyHasSectionDetail(units) || totalQuestions > 0
}

export function isFixtureOutline(outlineSource?: OutlineSource): boolean {
  return outlineSource === 'fixture'
}

export function formatOutlineUnitLabel(unit: OutlineUnit, outlineSource?: OutlineSource): string {
  if (isFixtureOutline(outlineSource)) {
    return `Unit ${unit.id}: ${unit.title}`
  }
  return unit.title
}

export function formatOutlineSectionLabel(
  unit: OutlineUnit,
  section: OutlineSection,
  outlineSource?: OutlineSource,
): string {
  if (isFixtureOutline(outlineSource)) {
    return `Unit ${unit.id} > ${section.title}`
  }
  return section.title
}

export function formatTopicUnitLabel(unit: TopicFrequencyUnit): string {
  if (unit.title.trim()) return unit.title.trim()
  return `Unit ${unit.unit}`
}

export function outlineSourceNotice(outlineSource?: OutlineSource): string | null {
  switch (outlineSource) {
    case 'extracted':
      return 'Extracted from PDF table of contents — upload a full outline for corrections.'
    case 'uploaded':
      return 'Custom outline uploaded.'
    case 'auto_stub':
      return 'Auto-generated from page ranges — upload a full outline for finer sections.'
    default:
      return null
  }
}

/** @deprecated Use outlineSourceNotice */
export function outlineStubNotice(outlineSource?: OutlineSource): string | null {
  return outlineSourceNotice(outlineSource)
}

export function topicFrequencyEmptyMessage(
  totalQuestions: number,
  unitCount: number,
  _sourceDocCount: number,
  coverageNote: string,
): string {
  if (unitCount > 0 || totalQuestions > 0) {
    return 'No past-paper units indexed for this course yet.'
  }
  if (/no past_paper/i.test(coverageNote)) {
    return 'No past papers indexed yet. Upload a PDF and choose Past paper as the document type to see exam topic frequency.'
  }
  return 'Upload past exam papers to see topic frequency estimates for this course.'
}

export function coverageBannerClass(note: string): string {
  if (/partial/i.test(note)) return 'coverage-banner coverage-partial'
  if (/no past_paper/i.test(note)) return 'coverage-banner coverage-muted'
  if (/matched.*by keyword|outline topics by keyword/i.test(note)) {
    return 'coverage-banner coverage-keyword'
  }
  if (/no pyq seed/i.test(note)) return 'coverage-banner coverage-info'
  return 'coverage-banner coverage-info'
}

export function canManageOutline(outlineSource?: OutlineSource): boolean {
  return outlineSource !== 'fixture' && outlineSource !== undefined
}

export function canRebuildOutline(outlineSource?: OutlineSource): boolean {
  return outlineSource === 'auto_stub' || outlineSource === 'extracted'
}
