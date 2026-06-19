import { DevAuthBanner } from './components/DevAuthBanner'
import { AppRoutes } from './routes/AppRoutes'
import './App.css'
import './wave4a-theme.css'

const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

export default function App() {
  return (
    <>
      {!clerkPublishableKey && <DevAuthBanner />}
      <AppRoutes />
    </>
  )
}
