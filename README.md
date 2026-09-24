# Agentic Job AI

Upload a resume (PDF) and an AI agent built with **LangGraph** finds matching jobs, ranks them,
explains the skill gaps, builds a learning roadmap for each job, generates ATS scores with tailored resume bullet points,
and writes reviewed cover letters for the jobs you choose.

- **Backend:** FastAPI + LangGraph (`backend/`)
- **Frontend:** React + Vite (`supabase-react/`)
- **Containerization:** Docker & Docker Compose (`Dockerfile`, `docker-compose.yml`)
- **Auth, file storage, saved results:** Supabase
- **AI:** Gemini (resume parsing + job-matching embeddings), Groq (skill gaps, roadmaps, cover letters, ATS tailoring)
- **Jobs:** Adzuna and Jooble APIs

## How the agent works

```
parse_resume ─► build_search_query ─┬─► search_adzuna ─┬─► match_jobs
                       ▲            └─► search_jooble ─┘       │
                       └───────── too few matches: broader query┘
                                                                │ top 5 jobs
                       analyze_job subgraph × 5, in parallel ◄──┘
                       (find_skill_gap ─► build_roadmap)
                                    │
                       select_jobs  ── pauses: user picks jobs (interrupt)
                                    ├─► cover_letter subgraph × selected, in parallel
                                    │   (write ─► review ─► rewrite if rejected ─► finalize)
                                    └─► tailor_resume × selected, in parallel
                                        (ATS score + matched/missing keywords + STAR bullet rewrites)
```

| LangGraph feature | Where | Why |
|---|---|---|
| Reducers (`Annotated[list, operator.add]`) | `job_results`, `skill_gaps`, `roadmaps`, `cover_letters`, `tailored_resumes` | Parallel branches merge their results safely |
| Parallel fan-out (`Send`) | One branch per job / per application kit | Jobs, cover letters, and resume tailoring execute concurrently |
| Subgraphs with input/output schemas | `analyze_job`, `cover_letter` | Per-job logic is isolated and testable |
| Parallel nodes + fan-in edge | Adzuna and Jooble | Both sources are queried at once |
| Conditional edges / loops | Search widening, cover letter review loop | The agent decides what to do next |
| Human in the loop (`interrupt`, `Command(resume=...)`) | `select_jobs` | User chooses which jobs get cover letters & tailoring |
| Checkpointer (SQLite locally, Postgres in production) | Whole graph | Paused or crashed runs continue later without redoing finished work |
| `RetryPolicy` with a custom `retry_on` | LLM nodes | Retries rate limits / timeouts / 5xx only |
| Runtime context (`context_schema`) | `AgentContext` | API clients and settings are injected, so tests use fakes |
| Custom stream (`get_stream_writer`) | All nodes | Live progress messages in the website |

Code: `backend/agents/graph/workflow.py` (graph), `backend/agents/agent/` (nodes), `backend/main.py` (API).

## Setup

### Option A: Quickstart with Docker (Recommended)
Once you have Docker installed and your `.env` files prepared:
```bash
# From the project root
docker compose up --build
```
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000 (Health check: http://localhost:8000/health)

---

### Option B: Local Setup (Without Docker)

#### 0. First run on a new computer
The repo has no installed packages and no secrets, so:

1. Install **Python 3.12+** and **Node.js 20+**.
2. Copy `backend\.env.example` to `backend\.env` and fill in your keys.
3. Copy `supabase-react\.env.example` to `supabase-react\.env.local` and fill it in.
4. Run the steps in 1-3 below.

### 1. Supabase
Create a project, then in **SQL Editor** run:

```sql
create table if not exists results (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  resume_path text,
  result_json jsonb not null,
  created_at timestamptz not null default now()
);
alter table results enable row level security;
create policy "Users read own results" on results
  for select to authenticated using (auth.uid() = user_id);

insert into storage.buckets (id, name, public) values ('resumes', 'resumes', false)
  on conflict (id) do nothing;
create policy "Users upload own resumes" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'resumes' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "Users update own resumes" on storage.objects
  for update to authenticated
  using (bucket_id = 'resumes' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "Users read own resumes" on storage.objects
  for select to authenticated
  using (bucket_id = 'resumes' and (storage.foldername(name))[1] = auth.uid()::text);
```

> All commands below are **PowerShell** (the Windows default). PowerShell 5.1 does not
> support `&&`, so each command goes on its own line.
>
> Use the `.cmd` files to start things: they work even when Windows blocks PowerShell
> scripts ("running scripts is disabled on this system"). The matching `.ps1` files do the
> same, if script execution is enabled on your machine.

### 2. Backend (Python 3.12)
One-time setup, from the project folder:
```powershell
uv venv --python 3.12 backend\.venv
uv pip install --python backend\.venv -r backend\requirements-dev.txt
Copy-Item backend\.env.example backend\.env
```
Fill in your keys in `backend\.env`, then start the API:
```powershell
.\start-backend.cmd
```
Open http://localhost:8000/health - `missing_settings` should be empty.

Optional, to match jobs with a local model instead of Gemini (adds PyTorch, ~2.5 GB):
```powershell
uv pip install --python backend\.venv -r backend\requirements-local-embeddings.txt
```

### 3. Frontend
One-time setup:
```powershell
Copy-Item supabase-react\.env.example supabase-react\.env.local
```
Fill it in, then start the website in a **second** terminal:
```powershell
.\start-frontend.cmd
```
Open http://localhost:5173.

### Try the agent without the website
No Supabase needed:
```powershell
backend\.venv\Scripts\python -m agents.main path\to\resume.pdf
```

## Tests
```powershell
.\run-tests.cmd
```
The tests use fake services (no API keys, no network) and cover: the full graph run with
pause/resume, parallel analysis, search widening, the cover letter review loop, retries,
resuming a crashed run from a SQLite checkpoint without repeating finished work, API login
and ownership checks, and error messages.

Frontend checks:
```powershell
Set-Location supabase-react
npm run lint
npm run build
Set-Location ..
```

## Benchmark
```powershell
backend\.venv\Scripts\python backend\scripts\benchmark.py --runs 5
backend\.venv\Scripts\python backend\scripts\benchmark.py --pdf path\to\resume.pdf --runs 3
```
The first uses simulated delays (no keys needed), the second calls the real APIs.
Prints wall-clock time vs. the total time of all external calls (what running them one after
another would take), call counts, and how many calls a crashed run repeats when resumed.
Results are saved to `benchmark_results.json`.

## Notes from a live run (2026-09-20, sample resume)

- Full run: resume parsed, 32 jobs found (Adzuna + Jooble), top 5 analyzed, 2 cover letters written — **40s**.
- Benchmark on live APIs: **61s** wall clock vs **110s** if the same calls ran one after another (**1.76x**).
- Groq's free tier allows **8000 tokens per minute**, which several parallel LLM calls can exceed.
  `GroqLLM` therefore runs at most 2 calls at a time and lets the SDK wait out `429`s;
  raising `max_parallel` in `agents/services.py` gets a bigger speed-up on a paid tier.
- Groq model names change: `llama-3.1-8b-instant` was retired, the default is now `openai/gpt-oss-120b`.
  Check <https://console.groq.com/docs/models> and set `GROQ_MODEL` if it stops working.

## Deployment

### Backend on Railway
`backend/railway.json` and `backend/Procfile` are ready.

1. Push this project to GitHub.
2. Railway → **New Project** → **Deploy from GitHub repo** → pick the repo.
3. Open the service → **Settings** → set **Root Directory** to `backend`.
4. **Variables** → add (from your `backend/.env`):
   `SUPABASE_URL`, `SUPABASE_KEY` (service role), `GEMINI_API_KEY`, `GROQ_API_KEY`,
   `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `JOOBLE_API_KEY`,
   `GEMINI_MODEL`, `GROQ_MODEL`, `EMBEDDING_PROVIDER=gemini`,
   `JOB_LOCATION`, `ADZUNA_COUNTRY`,
   `DATABASE_URL` (Supabase → Settings → Database → Session pooler string),
   and `ALLOWED_ORIGINS` set to your Netlify URL.
5. **Settings → Networking → Generate Domain**, then open `https://<your-app>.up.railway.app/health`.
   `missing_settings` must be empty.

Railway sets `PORT` itself, so do not set it. `render.yaml` is included too if you ever prefer Render.

### Frontend on Netlify
`netlify.toml` is ready (base `supabase-react`, publish `dist`).

1. Netlify → **Add new site** → **Import an existing project** → pick the repo.
2. **Environment variables**: `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`,
   `VITE_BACKEND_URL` (your Railway URL, no trailing slash).
3. Deploy, then copy the Netlify URL into Railway's `ALLOWED_ORIGINS` and redeploy the backend.

### Supabase
1. SQL Editor → run the SQL in step 1 above (table, bucket, access rules).
2. **Authentication → URL Configuration** → Site URL = your Netlify URL.
3. **Authentication → Sign In / Providers → Email** → turn **Confirm email** off for instant signups,
   or leave it on and users confirm by email first.

Notes:
- Keep `EMBEDDING_PROVIDER=gemini` when deploying: `local` pulls in PyTorch (~2.5 GB) and
  will not fit a free instance.
- Run a single server process: live progress messages are kept in memory per process
  (the analysis itself lives in the checkpointer).
- Render's free plan sleeps after inactivity, so the first request can take ~1 minute.
