import type { QueryPreset } from '../types'

export interface QueryPresetOption {
  value: QueryPreset
  label: string
  hint: string
  submitLabel: string
}

export const QUERY_PRESET_OPTIONS: QueryPresetOption[] = [
  {
    value: 'study',
    label: 'Study',
    hint: 'Ask a question — cited answer',
    submitLabel: 'Ask',
  },
  {
    value: 'summary',
    label: 'Summary',
    hint: 'Bullet summary from your notes',
    submitLabel: 'Summarize',
  },
  {
    value: 'flashcards',
    label: 'Flashcards',
    hint: 'Q/A flashcard pairs',
    submitLabel: 'Generate',
  },
  {
    value: 'exam',
    label: 'Exam',
    hint: 'Past-paper style Q&A from your ingested exam papers',
    submitLabel: 'Practice',
  },
]

export const DEFAULT_EXAM_EXAMPLE_QUESTIONS = [
  'Questions on lexemes and tokens',
  'Abstract data types in past exam papers',
] as const

export const DEFAULT_QUERY_PRESET: QueryPreset = 'study'

export function getQueryPresetOption(preset: QueryPreset): QueryPresetOption {
  return QUERY_PRESET_OPTIONS.find((option) => option.value === preset) ?? QUERY_PRESET_OPTIONS[0]
}

export function isExamPreset(preset: QueryPreset | undefined): boolean {
  return preset === 'exam'
}

export function isStudyPreset(preset: QueryPreset | undefined): boolean {
  return preset === 'study' || preset === 'summary' || preset === 'flashcards'
}
