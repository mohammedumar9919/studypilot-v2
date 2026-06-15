type TokenGetter = () => Promise<string | null>

let tokenGetter: TokenGetter | null = null

export function registerAuthTokenGetter(getter: TokenGetter): void {
  tokenGetter = getter
}

export function unregisterAuthTokenGetter(): void {
  tokenGetter = null
}

export async function authFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const headers = new Headers(init?.headers)

  if (tokenGetter) {
    try {
      const token = await tokenGetter()
      if (token) {
        headers.set('Authorization', `Bearer ${token}`)
      }
    } catch {
      // Proceed without auth header if token retrieval fails
    }
  }

  return fetch(input, { ...init, headers })
}
