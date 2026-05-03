import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import './App.css'

export default function Results({ user, setShowResults }) {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  // useEffect(() => {
  //   if (user) {
  //     fetchResults()
  //   }
  // }, [user])
  useEffect(() => {fetchResults()}, [])

  const fetchResults = async () => {
    const { data, error } = await supabase
      .from('results')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false })

    if (error) {
      console.error(error)
    } else {
      setResults(data)
    }
    setLoading(false)
  }
  if (loading) {
    return <p>Loading...</p>
  }
  return (
    <div className="container">
      <div className="results-page">

        <h2>🤖 AI Results</h2>

        <button onClick={() => setShowResults(false)}>
          ⬅ Back
        </button>

        {results.length === 0 ? ( 
          <p>No results yet</p>
        ) 
        : 
        (
          results.map((item) => {
          const data = item.result_json || {}

          return (
              <div key={item.id} className="result-card">
                {/* ---------------- JOBS ---------------- */}
                  <h3>💼 Top Jobs</h3>
                  {!data.top_jobs || data.top_jobs.length === 0 ? (
                    <p>No jobs found</p>
                  ) : (
                    data.top_jobs.map((job, i) => (
                      <div key={i} className="job-card">
                        <p><strong>{job.job_title}</strong></p>
                        <p>{job.company}</p>
                        <p>Score: {job.score}</p>
                        {job.apply_link && (
                          <a href={job.apply_link} target="_blank" rel="noopener noreferrer">
                            Apply →
                          </a>
                        )}
                      </div>
                    ))
                  )}

                  {/* ---------------- SKILLS ---------------- */}
                  <h3>📊 Skill Gaps</h3>
                  {!data.skill_gaps || data.skill_gaps.length === 0 ? (
                    <p>No gaps</p>
                  ) : (
                    <ul>
                      {data.skill_gaps.map((skill, i) => (
                      <li key={i}>
                        <strong>{skill.job_title}</strong>:{" "}
                        {Array.isArray(skill.missing_skills)
                          ? skill.missing_skills.join(", ")
                          : "N/A"}
                      </li>
                    ))}
                    </ul>
                  )}

                  {/* ---------------- ROADMAP ---------------- */}
                  <h3>🧠 Roadmap</h3>
                  {!data.roadmap || data.roadmap.length === 0 ? (
                    <p>No roadmap</p>
                  ) : (
                    data.roadmap.map((companyData, i) => (
                      <div key={i} className="roadmap-card">

                        <h4>🏢 {companyData.company}</h4>

                        {Array.isArray(companyData.roadmap) &&
                          companyData.roadmap.map((phase, j) => (
                            <div key={j} className="phase-card">

                              <p><strong>{phase.phase || "No phase"}</strong></p>

                              <p>
                                🎯 Focus:{" "}
                                {Array.isArray(phase.focus)
                                  ? phase.focus.join(", ")
                                  : "N/A"}
                              </p>

                              <ul>
                                {Array.isArray(phase.tasks) ? (
                                  phase.tasks.map((task, k) => (
                                    <li key={k}>{task}</li>
                                  ))
                                ) : (
                                  <li>No tasks available</li>
                                )}
                              </ul>

                            </div>
                          ))}

                      </div>
                    ))
                  )}
              </div>
            )
          })
        )}

      </div>
    </div>
  )
}