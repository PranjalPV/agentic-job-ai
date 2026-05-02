import { useState } from 'react'
import { supabase } from './supabaseClient'
import './App.css'
import Results from './Results'

export default function Dashboard({ user, setUser }) {
  const [file, setFile] = useState(null)
  const [showResults, setShowResults] = useState(false)
  const [loading, setLoading] = useState(false)
  const [uploaded, setUploaded] = useState(false)

  const handleUpload = async () => {
    if (!file) {
      alert("Please select a file")
    
      return
    }

    const filePath = `${user.id}/${file.name}`

    const { error } = await supabase.storage
      .from('resumes')
      .upload(filePath, file, { upsert: true })

    if (error) {
      alert(error.message)
    } else {
      alert("Resume uploaded successfully ✅")
      setUploaded(true)
    }
  }

  const handleAnalyze = async () => {
    if (!file) {
      alert("Upload resume first")
      return
    }

    const filePath = `${user.id}/${file.name}`

    setLoading(true)

    try {
      const res = await fetch(`${import.meta.env.VITE_BACKEND_URL}/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_id: user.id,
          file_path: filePath,
        }),
      })

      if (!res.ok) {
        throw new Error("Failed to analyze")
      }

      alert("Analysis complete ✅")

      // 🔥 auto move to results
      setShowResults(true)

    } catch (err) {
      console.error(err)
      alert("Error connecting to backend")
    }

    setLoading(false)
  }

if (showResults) {
  return <Results user={user} setShowResults={setShowResults} />
}

  return (
    <div className="container">
      <div className="auth-box">

        <h2>Upload Resume</h2>

        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files[0])}
        />

        <button className="btn upload" onClick={handleUpload}>
          Upload Resume
        </button>

        <button className="btn analyze" onClick={handleAnalyze} disabled={loading || !uploaded}>
          {loading ? "Analyzing..." : "Analyze / Find Jobs"}
        </button>

        <button onClick={() => setShowResults(true)}>
          View Results
        </button>

        <button
          className="btn logout"
          onClick={async () => {
            await supabase.auth.signOut()
            setUser(null)
          }}
        >
          Logout
        </button>

      </div>
    </div>
  )
}