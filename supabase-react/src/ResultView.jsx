import { useState } from 'react'

function MatchScore({ score }) {
  if (typeof score !== "number") return null
  const percent = Math.round(score * 100)
  return (
    <div className="match">
      <div className="match-value">{percent}%</div>
      <div className="match-label">match</div>
      <div className="match-bar"><span style={{ width: `${Math.min(100, percent)}%` }} /></div>
    </div>
  )
}

function Roadmap({ roadmap }) {
  if (!Array.isArray(roadmap) || roadmap.length === 0) return null
  return (
    <details className="disclosure">
      <summary>
        🧭 Learning roadmap
        <span className="summary-tag">{roadmap.length} phases</span>
      </summary>
      <div className="body">
        {roadmap.map((phase, i) => (
          <div key={i} className="phase">
            <div className="phase-name">{phase.phase || `Phase ${i + 1}`}</div>
            {Array.isArray(phase.focus) && phase.focus.length > 0 && (
              <div className="phase-focus">Focus: {phase.focus.join(", ")}</div>
            )}
            <ul>
              {(Array.isArray(phase.tasks) ? phase.tasks : []).map((task, k) => (
                <li key={k}>{task}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </details>
  )
}

function CoverLetter({ letter }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(letter.cover_letter)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <details className="disclosure">
      <summary>
        ✉️ Cover letter
        <span className="summary-tag">
          {typeof letter.review_score === "number" ? `reviewed ${letter.review_score}/5` : "draft"}
          {letter.drafts > 1 ? ` · ${letter.drafts} drafts` : ""}
        </span>
      </summary>
      <div className="body">
        <pre className="letter">{letter.cover_letter}</pre>
        <div className="letter-actions">
          <button className="ghost" onClick={copy}>{copied ? "Copied" : "Copy letter"}</button>
        </div>
      </div>
    </details>
  )
}

function TailoredResume({ tailored }) {
  const [copiedSummary, setCopiedSummary] = useState(false)
  const [copiedBullets, setCopiedBullets] = useState(false)

  if (!tailored) return null

  const copySummary = async () => {
    try {
      await navigator.clipboard.writeText(tailored.tailored_summary || "")
      setCopiedSummary(true)
      setTimeout(() => setCopiedSummary(false), 2000)
    } catch {
      setCopiedSummary(false)
    }
  }

  const copyBullets = async () => {
    try {
      const bullets = (tailored.tailored_bullet_points || []).map((b) => `• ${b}`).join("\n")
      await navigator.clipboard.writeText(bullets)
      setCopiedBullets(true)
      setTimeout(() => setCopiedBullets(false), 2000)
    } catch {
      setCopiedBullets(false)
    }
  }

  const matched = Array.isArray(tailored.matched_keywords) ? tailored.matched_keywords : []
  const missing = Array.isArray(tailored.missing_critical_keywords) ? tailored.missing_critical_keywords : []
  const bullets = Array.isArray(tailored.tailored_bullet_points) ? tailored.tailored_bullet_points : []
  const recommendations = Array.isArray(tailored.ats_recommendations) ? tailored.ats_recommendations : []

  return (
    <details className="disclosure">
      <summary>
        🎯 ATS Match & Tailored Resume
        <span className="summary-tag">
          {typeof tailored.ats_score === "number" ? `ATS Score ${tailored.ats_score}%` : "Tailored"}
        </span>
      </summary>
      <div className="body">
        <div style={{ marginBottom: "12px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
            <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-muted)" }}>Target Role ATS Alignment</span>
            <span style={{ fontSize: "0.95rem", fontWeight: 700, color: tailored.ats_score >= 75 ? "#10b981" : "#f59e0b" }}>
              {tailored.ats_score}%
            </span>
          </div>
          <div className="match-bar">
            <span
              style={{
                width: `${Math.min(100, tailored.ats_score || 0)}%`,
                background: tailored.ats_score >= 75 ? "linear-gradient(90deg, #10b981, #34d399)" : "linear-gradient(90deg, #f59e0b, #fbbf24)"
              }}
            />
          </div>
        </div>

        {matched.length > 0 && (
          <div className="job-section" style={{ marginTop: "10px" }}>
            <div className="job-section-label">Matched ATS Keywords</div>
            <div className="chips">
              {matched.map((kw, idx) => (
                <span key={idx} className="chip ok">{kw}</span>
              ))}
            </div>
          </div>
        )}

        {missing.length > 0 && (
          <div className="job-section" style={{ marginTop: "8px" }}>
            <div className="job-section-label">Keywords to Add (ATS Gaps)</div>
            <div className="chips">
              {missing.map((kw, idx) => (
                <span key={idx} className="chip gap">{kw}</span>
              ))}
            </div>
          </div>
        )}

        {tailored.tailored_summary && (
          <div className="job-section" style={{ marginTop: "14px" }}>
            <div className="job-section-label" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>Tailored Professional Summary</span>
              <button className="ghost" style={{ padding: "2px 8px", fontSize: "0.75rem" }} onClick={copySummary}>
                {copiedSummary ? "Copied" : "Copy summary"}
              </button>
            </div>
            <p className="page-sub" style={{ marginTop: "4px", fontSize: "0.88rem", lineHeight: 1.5, background: "rgba(255,255,255,0.03)", padding: "10px", borderRadius: "6px" }}>
              {tailored.tailored_summary}
            </p>
          </div>
        )}

        {bullets.length > 0 && (
          <div className="job-section" style={{ marginTop: "14px" }}>
            <div className="job-section-label" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>STAR-Method Tailored Bullets</span>
              <button className="ghost" style={{ padding: "2px 8px", fontSize: "0.75rem" }} onClick={copyBullets}>
                {copiedBullets ? "Copied" : "Copy bullets"}
              </button>
            </div>
            <ul style={{ paddingLeft: "18px", marginTop: "6px", fontSize: "0.88rem", lineHeight: 1.5 }}>
              {bullets.map((b, idx) => (
                <li key={idx} style={{ marginBottom: "6px" }}>{b}</li>
              ))}
            </ul>
          </div>
        )}

        {recommendations.length > 0 && (
          <div className="job-section" style={{ marginTop: "12px", borderTop: "1px dashed var(--border)", paddingTop: "10px" }}>
            <div className="job-section-label">💡 ATS Strategy Tips</div>
            <ul style={{ paddingLeft: "18px", marginTop: "4px", fontSize: "0.82rem", color: "var(--text-muted)" }}>
              {recommendations.map((tip, idx) => (
                <li key={idx}>{tip}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </details>
  )
}

function JobCard({ job, gap, roadmap, letter, tailored }) {
  const missing = Array.isArray(gap?.missing_skills) ? gap.missing_skills : []

  return (
    <article className="job-card">
      <div className="job-top">
        <div>
          <div className="job-title">{job.title || job.job_title || "Untitled role"}</div>
          <div className="job-meta">
            {job.company}
            {job.location ? ` · ${job.location}` : ""}
            {job.source && <span className="source-badge">{job.source}</span>}
          </div>
        </div>
        <MatchScore score={job.score} />
      </div>

      {gap && (
        <div className="job-section">
          <div className="job-section-label">Skills to learn</div>
          {missing.length > 0 ? (
            <div className="chips">
              {missing.map((skill, i) => <span key={i} className="chip gap">{skill}</span>)}
            </div>
          ) : (
            <div className="chips"><span className="chip ok">You already have the listed skills</span></div>
          )}
        </div>
      )}

      {(roadmap || letter || tailored) && (
        <>
          <Roadmap roadmap={roadmap?.roadmap} />
          {tailored && <TailoredResume tailored={tailored} />}
          {letter && <CoverLetter letter={letter} />}
        </>
      )}

      {job.apply_link && (
        <div className="job-links">
          <a className="apply-link" href={job.apply_link} target="_blank" rel="noopener noreferrer">
            Apply on {job.source || "site"} ↗
          </a>
        </div>
      )}
    </article>
  )
}

function Profile({ profile }) {
  if (!profile) return null
  const skills = Array.isArray(profile.skills) ? profile.skills : []

  return (
    <section className="card">
      <h3 className="card-title">👤 Your profile</h3>
      <div className="profile-grid">
        {profile.name && <div><span>Name</span>{profile.name}</div>}
        {profile.suggested_role && <div><span>Best fit role</span>{profile.suggested_role}</div>}
        {profile.experience_level && <div><span>Level</span>{profile.experience_level}</div>}
        <div><span>Skills found</span>{skills.length}</div>
      </div>
      {profile.summary && <p className="page-sub">{profile.summary}</p>}
      {skills.length > 0 && (
        <div className="job-section">
          <div className="job-section-label">Skills from your resume</div>
          <div className="chips">
            {skills.map((skill, i) => <span key={i} className="chip">{skill}</span>)}
          </div>
        </div>
      )}
    </section>
  )
}

export default function ResultView({ data, showCoverLetters = true, showProfile = true }) {
  const jobs = Array.isArray(data?.top_jobs) ? data.top_jobs : []
  const gaps = Array.isArray(data?.skill_gaps) ? data.skill_gaps : []
  const roadmaps = Array.isArray(data?.roadmap) ? data.roadmap : []
  const letters = Array.isArray(data?.cover_letters) ? data.cover_letters : []
  const tailored = Array.isArray(data?.tailored_resumes) ? data.tailored_resumes : []

  const byJob = (items) => new Map(items.map((item, i) => [item.job_id ?? i, item]))
  const gapFor = byJob(gaps)
  const roadmapFor = byJob(roadmaps)
  const letterFor = byJob(letters)
  const tailoredFor = byJob(tailored)

  if (jobs.length === 0) {
    return <p className="empty">No jobs found for this resume.</p>
  }

  return (
    <>
      {showProfile && <Profile profile={data?.profile} />}

      <section className="card">
        <h3 className="card-title">
          💼 Matched jobs <span className="count">{jobs.length}</span>
        </h3>
        <div className="job-list">
          {jobs.map((job, i) => {
            const id = job.id ?? i
            return (
              <JobCard
                key={id}
                job={job}
                gap={gapFor.get(id)}
                roadmap={roadmapFor.get(id)}
                letter={showCoverLetters ? letterFor.get(id) : null}
                tailored={tailoredFor.get(id)}
              />
            )
          })}
        </div>
      </section>
    </>
  )
}
