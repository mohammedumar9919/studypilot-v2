const STORAGE_KEY = 'studypilot:outline-confirm-dismiss'

function readDismissed(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    return JSON.parse(raw) as Record<string, boolean>
  } catch {
    return {}
  }
}

export function isOutlineConfirmDismissed(courseId: string): boolean {
  const key = courseId.trim()
  if (!key) return false
  return Boolean(readDismissed()[key])
}

export function dismissOutlineConfirm(courseId: string): void {
  const key = courseId.trim()
  if (!key) return
  const dismissed = readDismissed()
  dismissed[key] = true
  localStorage.setItem(STORAGE_KEY, JSON.stringify(dismissed))
}

export function clearOutlineConfirmDismiss(courseId: string): void {
  const key = courseId.trim()
  if (!key) return
  const dismissed = readDismissed()
  delete dismissed[key]
  localStorage.setItem(STORAGE_KEY, JSON.stringify(dismissed))
}
