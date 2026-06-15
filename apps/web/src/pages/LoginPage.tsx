import { SignIn } from '@clerk/clerk-react'
import { Navigate } from 'react-router-dom'

const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

export function LoginPage() {
  if (!clerkPublishableKey) {
    return <Navigate to="/courses" replace />
  }

  return (
    <div className="login-page">
      <SignIn routing="path" path="/login" signUpUrl="/login" />
    </div>
  )
}
