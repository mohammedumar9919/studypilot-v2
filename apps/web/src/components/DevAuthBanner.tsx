export function DevAuthBanner() {
  return (
    <div className="dev-auth-banner" role="status">
      Dev mode — Clerk auth disabled. API uses{' '}
      <code>STUDYPILOT_AUTH_DISABLED=1</code> on localhost.
    </div>
  )
}
