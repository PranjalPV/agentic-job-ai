import { useState } from 'react'
import { supabase } from './supabaseClient'
import { api } from './api'
import './App.css'
import Layout from './Layout'
import Analysis from './Analysis'
import Results from './Results'

const MAX_FILE_BYTES = 5 * 1024 * 1024

function activeAnalysisKey(userId) {
  return `active-analysis:${userId}`
}

function readActiveAnalysis(userId) {
  try {
    return localStorage.getItem(activeAnalysisKey(userId))
  } catch {
    return null
  }
}

function writeActiveAnalysis(userId, threadId) {
  try {
    if (threadId) localStorage.setItem(activeAnalysisKey(userId), threadId)
    else localStorage.removeItem(activeAnalysisKey(userId))
  } catch {
    // storage unavailable: the analysis just won't reopen after a refresh
  }
}

function UploadPanel({ file, onFile, onStart, loading, status, error, threadId, onOpen, onResults }) {
  return (
    <>
      <div className="page-head">
        <h1>Find your next role</h1>
        <p className="page-sub">
          Upload your resume and the agent finds matching jobs, the skills you&apos;re missing,
          a learning plan and cover letters.
        </p>
      </div>

      <section className="card">
        <h3 className="card-title">📄 Your resume</h3>

        <label className="upload-zone">
          <input
            type="file"
            accept="application/pdf"
            disabled={loading}
            onChange={(e) => onFile(e.target.files[0] ?? null)}
          />
          <span className="upload-icon">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 16V4" /><path d="m7 9 5-5 5 5" />
              <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
            </svg>
          </span>
          {file
            ? <span className="file-chip">📎 {file.name}</span>
            : <strong>Choose a PDF resume</strong>}
          <span className="upload-hint">PDF with selectable text, up to 5 MB</span>
        </label>

        <div className="actions-row">
          <button className="primary" onClick={onStart} disabled={loading || !file}>
            {loading ? "Starting…" : "Analyze my resume"}
          </button>
          {threadId && (
            <button className="ghost" onClick={onOpen} disabled={loading}>
              Open latest analysis
            </button>
          )}
          <button className="ghost" onClick={onResults} disabled={loading}>
            Past results
          </button>
        </div>

        {status && <div className="notice info"><span className="spinner" />{status}</div>}
        {error && <div className="notice error">{error}</div>}
      </section>

      <section className="card">
        <h3 className="card-title">How it works</h3>
        <div className="steps">
          <div className="step"><span className="step-number">1</span>
            <span>Your resume is read and turned into a skills profile.</span></div>
          <div className="step"><span className="step-number">2</span>
            <span>Two job boards are searched, and the best 5 matches are ranked.</span></div>
          <div className="step"><span className="step-number">3</span>
            <span>Each job gets a skill-gap check and a week-by-week learning plan.</span></div>
          <div className="step"><span className="step-number">4</span>
            <span>You choose the jobs that get a reviewed, fact-checked cover letter.</span></div>
        </div>
      </section>
    </>
  )
}

export default function Dashboard({ user, setUser }) {
  const [file, setFile] = useState(null)
  const [view, setView] = useState('upload')
  const [threadId, setThreadId] = useState(() => readActiveAnalysis(user.id))
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  const handleUploadAndAnalyze = async () => {
    if (!file) {
      setError("Please choose your resume (PDF) first")
      return
    }
    if (file.type !== "application/pdf") {
      setError("Please upload a PDF file")
      return
    }
    if (file.size > MAX_FILE_BYTES) {
      setError("Your resume is larger than 5 MB. Please upload a smaller PDF.")
      return
    }

    setLoading(true)
    setError('')

    try {
      // 1) Upload resume
      setStatus("Uploading your resume…")
      const safeName = file.name.replace(/[^\w.-]+/g, "_")
      const filePath = `${user.id}/${safeName}`

      const { error: uploadError } = await supabase.storage
        .from('resumes')
        .upload(filePath, file, { upsert: true })

      if (uploadError) {
        throw new Error(uploadError.message)
      }

      // 2) Start the agent on the uploaded resume
      setStatus("Starting analysis…")
      const { thread_id } = await api.startAnalysis(filePath)

      writeActiveAnalysis(user.id, thread_id)
      setThreadId(thread_id)
      setStatus('')
      setView('analysis')

    } catch (err) {
      console.error(err)
      setStatus('')
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const forgetAnalysis = () => {
    writeActiveAnalysis(user.id, null)
    setThreadId(null)
    setView('upload')
    setError(
      "That analysis is no longer on the server (it may have restarted). " +
      "Finished analyses are still under Past results."
    )
  }

  const logout = async () => {
    await supabase.auth.signOut()
    setUser(null)
  }

  return (
    <Layout user={user} onLogout={logout}>
      {view === 'analysis' && threadId && (
        <Analysis
          threadId={threadId}
          onBack={() => setView('upload')}
          onMissing={forgetAnalysis}
        />
      )}

      {view === 'results' && (
        <Results user={user} onBack={() => setView('upload')} />
      )}

      {view === 'upload' && (
        <UploadPanel
          file={file}
          loading={loading}
          status={status}
          error={error}
          threadId={threadId}
          onFile={(next) => { setFile(next); setError('') }}
          onStart={handleUploadAndAnalyze}
          onOpen={() => setView('analysis')}
          onResults={() => setView('results')}
        />
      )}
    </Layout>
  )
}
