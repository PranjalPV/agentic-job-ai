import './App.css'

export function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
           strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.2-3.2" />
        <path d="M8.5 11.5 10.5 13.5 14 9.5" />
      </svg>
    </span>
  )
}

export function Brand({ withTag = true }) {
  return (
    <div className="brand">
      <BrandMark />
      <span>
        <span className="brand-name">Agentic Job AI</span>
        {withTag && <span className="brand-tag">Resume to jobs, gaps and cover letters</span>}
      </span>
    </div>
  )
}

export default function Layout({ user, onLogout, children }) {
  return (
    <>
      <header className="app-header">
        <Brand />
        {user && (
          <div className="header-user">
            <span className="header-email">{user.email}</span>
            <button className="ghost" onClick={onLogout}>Log out</button>
          </div>
        )}
      </header>
      <main className="page">{children}</main>
    </>
  )
}
