import { useAuth } from '@clerk/clerk-react'
import { useEffect, type ReactNode } from 'react'

import { registerAuthTokenGetter, unregisterAuthTokenGetter } from '../api/authFetch'

export function AuthFetchProvider({ children }: { children: ReactNode }) {
  const { getToken } = useAuth()

  useEffect(() => {
    registerAuthTokenGetter(() => getToken())
    return () => unregisterAuthTokenGetter()
  }, [getToken])

  return children
}
