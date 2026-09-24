import { useEffect, useState } from 'react'
import { api } from './api'
import ResultView from './ResultView'
import './App.css'

const POLL_INTERVAL_MS = 2000

function JobSelection({ jobs, selected, onToggle, onWrite, onSkip, busy, title, subtitle }) {
  return (
    <section className="card">
      <div className="select-head">
        <div>
          <h3 className="card-title" style={{ marginBottom: 4 }}>{title}</h3>
          <p className="page-sub">{subtitle}</p>
        </div>
      </div>

      <div className="job-list">
        {jobs.map((job) => (
          <label
            key={job.id}
            className={`job-card selectable ${selected.includes(job.id) ? "selected" : ""}`}
          >
            <div className="checkbox">
              <input
                type="checkbox"
                checked={selected.includes(job.id)}
                disabled={busy}
                onChange={() => onToggle(job.id)}
              />
              <div>
                <div className="job-title">{job.title}</div>
                <div className="job-meta">{job.company}</div>
              </div>
            </div>
          </label>
        ))}
      </div>

      <div className="actions-row">
        <button className="primary" disabled={busy || selected.length === 0} onClick={onWrite}>
          {selected.length > 0
            ? `Write ${selected.length} cover letter${selected.length === 1 ? "" : "s"}`
            : "Write cover letters"}
        </button>
        {onSkip && (
          <button className="ghost" disabled={busy} onClick={onSkip}>
            Skip for now
          </button>
        )}
      </div>
    </section>
  )
}

export default function Analysis({ threadId, onBack, onMissing }) {
  const [analysis, setAnalysis] = useState(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  const status = analysis?.status

  // Poll while the backend is working
  useEffect(() => {
    let cancelled = false
    let timer

    const poll = async () => {
      try {
        const data = await api.getAnalysis(threadId)
        if (cancelled) return
        setAnalysis(data)
        setError('')
        if (data.status === "processing") {
          timer = setTimeout(poll, POLL_INTERVAL_MS)
        }
      } catch (err) {
        if (cancelled) return
        setError(err.message)
        if (err.status === 404) {
          // The server no longer has this run (e.g. it restarted).
          // Finished analyses are still saved under Past results.
          onMissing?.()
        } else if (err.status !== 401) {
          // Temporary network problem: keep trying
          timer = setTimeout(poll, POLL_INTERVAL_MS * 2)
        }
      }
    }

    poll()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId, refreshKey])

  const runAction = async (action) => {
    setSubmitting(true)
    setError('')
    try {
      await action()
      setSelected([])
      // Keep the results on screen while the next step runs
      setAnalysis((current) => current && { ...current, status: "processing" })
      setRefreshKey((key) => key + 1)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const toggleJob = (jobId) => {
    setSelected((current) =>
      current.includes(jobId) ? current.filter((id) => id !== jobId) : [...current, jobId]
    )
  }

  const progress = analysis?.progress ?? []
  const result = analysis?.result
  const hasResults = Array.isArray(result?.top_jobs) && result.top_jobs.length > 0

  // Jobs that don't have a cover letter yet, so more can be written later
  const written = new Set((result?.cover_letters ?? []).map((letter) => letter.job_id))
  const jobsWithoutLetter = (result?.top_jobs ?? [])
    .filter((job) => !written.has(job.id))
    .map((job) => ({ id: job.id, title: job.title, company: job.company }))

  return (
    <>
      <div className="back-link">
        <button className="link" onClick={onBack}>← Back to upload</button>
      </div>

      <div className="page-head">
        <h1>Resume analysis</h1>
        <p className="page-sub">
          {status === "done"
            ? "Finished — also saved under Past results."
            : "Matching your resume against live job listings."}
        </p>
      </div>

      {!analysis && !error && (
        <div className="card progress-card">
          <div className="progress-head"><span className="spinner" /><strong>Loading…</strong></div>
        </div>
      )}

      {error && <div className="notice error">{error}</div>}

      {status === "processing" && (
        <div className="card progress-card">
          <div className="progress-head">
            <span className="spinner" />
            <strong>{hasResults ? "Writing your cover letters…" : "Working on it…"}</strong>
          </div>
          {progress.length > 0 ? (
            <ul className="progress-list">
              {progress.slice(-6).map((message, i) => <li key={i}>{message}</li>)}
            </ul>
          ) : (
            <p className="page-sub">This usually takes under a minute.</p>
          )}
        </div>
      )}

      {(status === "error" || status === "stalled") && (
        <div className="card">
          <div className="notice error" style={{ marginTop: 0 }}>{analysis.message}</div>
          <div className="actions-row">
            {analysis.can_resume && (
              <button className="primary" disabled={submitting}
                      onClick={() => runAction(() => api.resumeAnalysis(threadId))}>
                Resume analysis
              </button>
            )}
            <button className="ghost" onClick={onBack}>Upload another resume</button>
          </div>
        </div>
      )}

      {status === "awaiting_selection" && (
        <JobSelection
          title="✉️ Write cover letters"
          subtitle="Pick the jobs you want a tailored, fact-checked letter for."
          jobs={analysis.selection.jobs}
          selected={selected}
          busy={submitting}
          onToggle={toggleJob}
          onWrite={() => runAction(() => api.selectJobs(threadId, selected))}
          onSkip={() => runAction(() => api.selectJobs(threadId, []))}
        />
      )}

      {status === "done" && jobsWithoutLetter.length > 0 && (
        <JobSelection
          title="✉️ Write more cover letters"
          subtitle="Changed your mind? Add letters for the other matched jobs."
          jobs={jobsWithoutLetter}
          selected={selected}
          busy={submitting}
          onToggle={toggleJob}
          onWrite={() => runAction(() => api.generateLetters(threadId, selected))}
        />
      )}

      {status === "done" && jobsWithoutLetter.length === 0 && (
        <div className="notice success">✅ Every matched job has a cover letter.</div>
      )}

      {/* Results stay on screen through every step, including while letters are written */}
      {hasResults && <ResultView data={result} />}
    </>
  )
}
