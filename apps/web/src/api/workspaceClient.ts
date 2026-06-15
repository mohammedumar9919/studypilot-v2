import { authFetch } from './authFetch'

const WORKSPACE_ME = '/api/v1/workspaces/me'
const WORKSPACE_COURSES = '/api/v1/workspaces/me/courses'

export class WorkspaceApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'WorkspaceApiError'
    this.status = status
  }
}

export interface WorkspaceMeResponse {
  id: string
  name: string
  slug: string
}

export interface WorkspaceCourse {
  id: string
  name: string
  structure_mode: 'corpus' | 'organized' | 'mapped'
  created_at: string
}

export interface CreateWorkspaceCourseRequest {
  id: string
  name?: string
}

async function parseWorkspaceError(response: Response): Promise<never> {
  let detail = response.statusText
  try {
    const payload = (await response.json()) as { detail?: string }
    if (payload.detail) detail = payload.detail
  } catch {
    // ignore parse errors
  }
  throw new WorkspaceApiError(detail, response.status)
}

export async function getWorkspaceMe(signal?: AbortSignal): Promise<WorkspaceMeResponse> {
  const response = await authFetch(WORKSPACE_ME, { signal })

  if (!response.ok) {
    return parseWorkspaceError(response)
  }

  return (await response.json()) as WorkspaceMeResponse
}

export async function listWorkspaceCourses(
  signal?: AbortSignal,
): Promise<WorkspaceCourse[]> {
  const response = await authFetch(WORKSPACE_COURSES, { signal })

  if (!response.ok) {
    return parseWorkspaceError(response)
  }

  return (await response.json()) as WorkspaceCourse[]
}

export async function createWorkspaceCourse(
  body: CreateWorkspaceCourseRequest,
): Promise<WorkspaceCourse> {
  const response = await authFetch(WORKSPACE_COURSES, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    return parseWorkspaceError(response)
  }

  return (await response.json()) as WorkspaceCourse
}
