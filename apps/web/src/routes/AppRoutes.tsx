import { SignedIn, SignedOut } from '@clerk/clerk-react'
import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { CoursesPage } from '../pages/CoursesPage'
import { LoginPage } from '../pages/LoginPage'
import { StudyWorkspacePage } from '../pages/StudyWorkspacePage'

const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

function ProtectedRoute({ children }: { children: ReactNode }) {
  if (!clerkPublishableKey) {
    return children
  }

  return (
    <>
      <SignedIn>{children}</SignedIn>
      <SignedOut>
        <Navigate to="/login" replace />
      </SignedOut>
    </>
  )
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Navigate to="/courses" replace />} />
      <Route
        path="/courses"
        element={
          <ProtectedRoute>
            <CoursesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/courses/:courseId"
        element={
          <ProtectedRoute>
            <StudyWorkspacePage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/courses" replace />} />
    </Routes>
  )
}
