import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  createWorkspaceCourse,
  listWorkspaceCourses,
  WorkspaceApiError,
  type WorkspaceCourse,
} from '../api/workspaceClient'
import { TrustBadges } from '../components/TrustBadges'
import '../App.css'
import '../wave4a-theme.css'

export function CoursesPage() {
  const [courses, setCourses] = useState<WorkspaceCourse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [newCourseId, setNewCourseId] = useState('')
  const [newCourseName, setNewCourseName] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const loadCourses = useCallback(() => {
    setLoading(true)
    setError(null)
    void listWorkspaceCourses()
      .then(setCourses)
      .catch((err) => {
        if (err instanceof WorkspaceApiError) {
          setError(`${err.status}: ${err.message}`)
        } else {
          setError(err instanceof Error ? err.message : 'Failed to load courses')
        }
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadCourses()
  }, [loadCourses])

  const handleCreate = (event: FormEvent) => {
    event.preventDefault()
    const id = newCourseId.trim()
    if (!id) return

    setCreating(true)
    setCreateError(null)
    void createWorkspaceCourse({
      id,
      name: newCourseName.trim() || undefined,
    })
      .then(() => {
        setNewCourseId('')
        setNewCourseName('')
        loadCourses()
      })
      .catch((err) => {
        if (err instanceof WorkspaceApiError) {
          setCreateError(`${err.status}: ${err.message}`)
        } else {
          setCreateError(err instanceof Error ? err.message : 'Failed to create course')
        }
      })
      .finally(() => setCreating(false))
  }

  return (
    <div className="app-shell">
      <div className="ambient-streaks" aria-hidden="true" />
      <div className="app courses-page">
        <header className="app-header reveal-on-load">
          <div className="app-header-main">
            <h1>
              Study<span className="gradient-accent">Pilot</span>
            </h1>
            <p className="subtitle">Your courses — pick one to study or create a new workspace</p>
          </div>
          <TrustBadges />
        </header>

        <main className="courses-page-main reveal-on-load reveal-delay-1">
          <section className="panel courses-create-panel">
            <h2>Create course</h2>
            <form className="courses-create-form" onSubmit={handleCreate}>
              <label>
                Course ID
                <input
                  type="text"
                  value={newCourseId}
                  onChange={(event) => setNewCourseId(event.target.value)}
                  placeholder="e.g. PPL"
                  required
                  minLength={2}
                  disabled={creating}
                />
              </label>
              <label>
                Display name <span className="muted">(optional)</span>
                <input
                  type="text"
                  value={newCourseName}
                  onChange={(event) => setNewCourseName(event.target.value)}
                  placeholder="Private Pilot Licence"
                  disabled={creating}
                />
              </label>
              <button type="submit" disabled={creating || newCourseId.trim().length < 2}>
                {creating ? 'Creating…' : 'Create course'}
              </button>
            </form>
            {createError && (
              <p className="courses-error" role="alert">
                {createError}
              </p>
            )}
          </section>

          <section className="panel courses-list-panel">
            <h2>Your courses</h2>
            {loading && <p className="muted">Loading courses…</p>}
            {error && (
              <p className="courses-error" role="alert">
                {error}
              </p>
            )}
            {!loading && !error && courses.length === 0 && (
              <p className="muted">No courses yet — create one above to get started.</p>
            )}
            {!loading && courses.length > 0 && (
              <ul className="courses-list">
                {courses.map((course) => (
                  <li key={course.id}>
                    <Link to={`/courses/${encodeURIComponent(course.id)}`} className="courses-list-link">
                      <span className="courses-list-id">{course.id}</span>
                      {course.name && course.name !== course.id && (
                        <span className="courses-list-name">{course.name}</span>
                      )}
                      <span className="courses-list-mode muted">{course.structure_mode}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </main>
      </div>
    </div>
  )
}
