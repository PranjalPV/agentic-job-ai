import { useState } from 'react'
import { supabase } from './supabaseClient'
import { Brand } from './Layout'
import './App.css'

export default function Auth({ setUser }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const missingFields = !email.trim() || !password

  const handleSignup = async () => {
    setBusy(true)
    setError('')
    setMessage('')

    const { data, error } = await supabase.auth.signUp({ email, password })

    if (error) {
      setError(error.message)
    } else if (data.session) {
      setUser(data.user)
    } else {
      // Email confirmation is switched on for this project
      setMessage("Account created. Check your email for the confirmation link, then log in.")
    }
    setBusy(false)
  }

  const handleLogin = async () => {
    setBusy(true)
    setError('')
    setMessage('')

    const { data, error } = await supabase.auth.signInWithPassword({ email, password })

    if (error) {
      setError(
        error.message === "Email not confirmed"
          ? "Please confirm your email first, then log in."
          : error.message
      )
    } else {
      setUser(data.user)
    }
    setBusy(false)
  }

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <Brand withTag={false} />
        <p className="auth-lead">
          Turn your resume into ranked jobs, skill gaps and cover letters.
        </p>

        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            placeholder="you@example.com"
            value={email}
            disabled={busy}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            placeholder="••••••••"
            value={password}
            disabled={busy}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !missingFields && !busy) handleLogin()
            }}
          />
        </div>

        <div className="auth-actions">
          <button className="primary" onClick={handleLogin} disabled={busy || missingFields}>
            Log in
          </button>
          <button className="ghost" onClick={handleSignup} disabled={busy || missingFields}>
            Sign up
          </button>
        </div>

        {message && <div className="notice info">{message}</div>}
        {error && <div className="notice error">{error}</div>}

        <p className="auth-footnote">Your resume and results stay private to your account.</p>
      </div>
    </div>
  )
}
