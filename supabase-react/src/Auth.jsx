import { useState, useEffect } from 'react'
import { supabase } from './supabaseClient'
import './App.css'

export default function Auth({ setUser }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')


  const handleSignup = async () => {
    const { error } = await supabase.auth.signUp({ email, password })
    if (error) alert(error.message)
    else alert("Signup successful")
  }

  const handleLogin = async () => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    })

    if (error) alert(error.message)
    else {
      alert("Login successful")
      setUser(data.user) // ✅ important
    }
  }



  return (
    <div className="container">
      <div className="auth-box">
        <h1>Login / Signup</h1>

        <input
          className="input-field"
          type="email"
          placeholder="Email"
          onChange={(e) => setEmail(e.target.value)}
        />

        <input
          className="input-field"
          type="password"
          placeholder="Password"
          onChange={(e) => setPassword(e.target.value)}
        />

        <button className="btn signup" onClick={handleSignup}>
          Sign Up
        </button>

        <button className="btn login" onClick={handleLogin}>
          Login
        </button>
      </div>
    </div>
  )
}