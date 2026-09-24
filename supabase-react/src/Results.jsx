import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import ResultView from './ResultView'
import './App.css'

function formatDate(value) {
  if (!value) return "Result"
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

export default function Results({ user, onBack }) {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    supabase
      .from('results')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false })
      .then(({ data, error }) => {
        if (cancelled) return
        if (error) {
          console.error(error)
          setError("Couldn't load your past results.")
        } else {
          setResults(data)
        }
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [user.id])

  return (
    <>
      <div className="back-link">
        <button className="link" onClick={onBack}>← Back to upload</button>
      </div>

      <div className="page-head">
        <h1>Past results</h1>
        <p className="page-sub">Every analysis you have run, newest first.</p>
      </div>

      {loading && (
        <div className="card progress-card">
          <div className="progress-head"><span className="spinner" /><strong>Loading…</strong></div>
        </div>
      )}

      {error && <div className="notice error">{error}</div>}

      {!loading && !error && results.length === 0 && (
        <div className="card">
          <p className="empty">No analyses yet. Upload a resume to get started.</p>
        </div>
      )}

      {results.map((item, index) => (
        <details key={item.id} className="card result-entry" open={index === 0}>
          <summary>
            <span className="when">{formatDate(item.created_at)}</span>
            <span className="what">
              {item.resume_path ? item.resume_path.split("/").pop() : ""}
              {" · "}
              {(item.result_json?.top_jobs?.length ?? 0)} jobs
              {item.result_json?.cover_letters?.length
                ? ` · ${item.result_json.cover_letters.length} letters`
                : ""}
            </span>
          </summary>
          <div style={{ marginTop: 16 }}>
            <ResultView data={item.result_json || {}} />
          </div>
        </details>
      ))}
    </>
  )
}
