-- pgvector schema for Supabase/Postgres
create extension if not exists vector;

create table if not exists knowledge_base (
  id uuid primary key default gen_random_uuid(),
  content text,
  metadata jsonb default '{}'::jsonb,
  embedding vector(384)
);

create or replace function match_documents(query_embedding vector(384), match_count int)
returns table (id uuid, content text, metadata jsonb, similarity float)
language sql
as $$
  select id, content, metadata,
         1 - (embedding <=> query_embedding) as similarity
  from knowledge_base
  order by embedding <=> query_embedding
  limit match_count;
$$;
