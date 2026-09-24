-- ============================================================================
-- Supabase pgvector Migration for Agentic Job AI
-- Shared Bounded Job Cache with HNSW Vector Index, 7-Day TTL & LRU Eviction
-- ============================================================================

-- 1. Enable the pgvector extension for high-performance vector operations
create extension if not exists vector;

-- 2. Create the shared public cached_jobs table
create table if not exists cached_jobs (
  id uuid primary key default gen_random_uuid(),
  fingerprint text unique not null,          -- md5(lower(title) + lower(company) + lower(location))
  title text not null,
  company text not null,
  location text,
  description text not null,
  apply_link text,
  source text not null,
  embedding vector(768),                     -- 768-dimensional dense vector (Gemini)
  created_at timestamptz not null default now(),
  last_accessed_at timestamptz not null default now()
);

-- 3. Create high-speed HNSW index for sub-15ms cosine similarity search
create index if not exists idx_cached_jobs_embedding 
  on cached_jobs using hnsw (embedding vector_cosine_ops);

-- Index for sliding TTL and LRU access sorting
create index if not exists idx_cached_jobs_created_at on cached_jobs (created_at desc);
create index if not exists idx_cached_jobs_last_accessed on cached_jobs (last_accessed_at desc);

-- 4. Vector Match Procedure (Filters for fresh jobs within max_age_days and updates LRU timestamp)
create or replace function match_cached_jobs (
  query_embedding vector(768),
  match_threshold float default 0.60,
  match_count int default 5,
  max_age_days int default 7
)
returns table (
  id uuid,
  title text,
  company text,
  location text,
  description text,
  apply_link text,
  source text,
  similarity float
)
language plpgsql
security definer
as $$
begin
  -- Update last_accessed_at for LRU tracking on matching records
  update cached_jobs
  set last_accessed_at = now()
  where id in (
    select c.id
    from cached_jobs c
    where c.created_at >= now() - (max_age_days || ' days')::interval
      and (1 - (c.embedding <=> query_embedding)) >= match_threshold
    order by (1 - (c.embedding <=> query_embedding)) desc
    limit match_count
  );

  -- Return matching fresh jobs sorted by cosine similarity
  return query
  select
    c.id,
    c.title,
    c.company,
    c.location,
    c.description,
    c.apply_link,
    c.source,
    (1 - (c.embedding <=> query_embedding)) as similarity
  from cached_jobs c
  where c.created_at >= now() - (max_age_days || ' days')::interval
    and (1 - (c.embedding <=> query_embedding)) >= match_threshold
  order by similarity desc
  limit match_count;
end;
$$;

-- 5. Bounded Cache Pruning: Strict 7-Day Purge & LRU Eviction (Cap: 5,000 jobs = ~20MB)
create or replace function prune_cached_jobs (
  max_capacity int default 5000,
  max_age_days int default 7
)
returns int
language plpgsql
security definer
as $$
declare
  purged_count int := 0;
  excess_count int := 0;
begin
  -- Step 1: Purge stale jobs older than max_age_days (Default: 7 days)
  delete from cached_jobs
  where created_at < now() - (max_age_days || ' days')::interval;
  get diagnostics purged_count = row_count;

  -- Step 2: LRU Eviction - If capacity exceeds max_capacity, prune least recently accessed
  select count(*) - max_capacity into excess_count from cached_jobs;
  if excess_count > 0 then
    delete from cached_jobs
    where id in (
      select id from cached_jobs
      order by last_accessed_at asc
      limit excess_count
    );
  end if;

  return purged_count;
end;
$$;
