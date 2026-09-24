import { supabase } from './supabaseClient'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL

async function authHeaders() {
  const { data } = await supabase.auth.getSession()
  const token = data?.session?.access_token
  if (!token) {
    throw new Error("Your session has expired. Please log in again.")
  }
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  }
}

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(`${BACKEND_URL}${path}`, {
      ...options,
      headers: await authHeaders(),
    })
  } catch {
    throw new Error("Couldn't connect to the server. Please try again.")
  }

  let body = null
  try {
    body = await res.json()
  } catch {
    // empty or non-JSON body
  }

  if (!res.ok) {
    const error = new Error(
      (typeof body?.detail === "string" && body.detail) || "Request failed. Please try again."
    )
    error.status = res.status
    throw error
  }
  return body
}

export const api = {
  startAnalysis: (filePath) =>
    request("/analyze", { method: "POST", body: JSON.stringify({ file_path: filePath }) }),

  getAnalysis: (threadId) => request(`/analyze/${threadId}`),

  selectJobs: (threadId, jobIds) =>
    request(`/analyze/${threadId}/select`, { method: "POST", body: JSON.stringify({ job_ids: jobIds }) }),

  generateLetters: (threadId, jobIds) =>
    request(`/analyze/${threadId}/letters`, { method: "POST", body: JSON.stringify({ job_ids: jobIds }) }),

  resumeAnalysis: (threadId) =>
    request(`/analyze/${threadId}/resume`, { method: "POST" }),
}
