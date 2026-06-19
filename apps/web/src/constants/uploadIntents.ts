import type { DocumentKind, UploadIntent } from '../types'

export type SelectableUploadIntent = 'quick' | 'syllabus'

export const UPLOAD_INTENT_OPTIONS: ReadonlyArray<{
  value: SelectableUploadIntent
  label: string
  helper: string
}> = [
  {
    value: 'quick',
    label: 'Quick study',
    helper: 'Ask your PDF — no course map sidebar',
  },
  {
    value: 'syllabus',
    label: 'Syllabus / course map',
    helper: 'Extract unit tree for sidebar (SP-052 promotion later)',
  },
]

export function showsUploadIntentPicker(docKind: DocumentKind): boolean {
  return docKind === 'notes' || docKind === 'textbook'
}

export function resolveUploadIntent(
  docKind: DocumentKind,
  choice: SelectableUploadIntent,
): UploadIntent {
  if (docKind === 'past_paper') return 'past_paper'
  if (docKind === 'syllabus') return 'syllabus'
  return choice
}
