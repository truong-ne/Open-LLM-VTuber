-- Operator migration; runtime never installs extensions implicitly.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE SCHEMA IF NOT EXISTS mao_hybrid;
CREATE TABLE IF NOT EXISTS mao_hybrid.schema_versions (
    version integer PRIMARY KEY, applied timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS mao_hybrid.memories (
    id bigserial PRIMARY KEY, scope text NOT NULL,
    kind text NOT NULL CHECK(kind IN ('long_term','social','skill')),
    subject text NOT NULL, content text NOT NULL CHECK(length(content)<=1000),
    content_hash text GENERATED ALWAYS AS (md5(content)) STORED,
    normalized text NOT NULL,
    search tsvector GENERATED ALWAYS AS (to_tsvector('simple', normalized)) STORED,
    source text NOT NULL CHECK(source IN ('unverified_claim','operator','evaluation')),
    created timestamptz NOT NULL DEFAULT now(), expires timestamptz NOT NULL,
    embedding vector(1024), embedding_model text,
    UNIQUE(scope,kind,subject,content_hash));
CREATE INDEX IF NOT EXISTS mao_memory_scope ON mao_hybrid.memories(scope,subject,kind,expires);
CREATE INDEX IF NOT EXISTS mao_memory_fts ON mao_hybrid.memories USING gin(search);
CREATE INDEX IF NOT EXISTS mao_memory_trgm ON mao_hybrid.memories USING gin(normalized gin_trgm_ops);
CREATE INDEX IF NOT EXISTS mao_memory_hnsw ON mao_hybrid.memories USING hnsw(embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS mao_hybrid.state (
    scope text NOT NULL,key text NOT NULL,value jsonb NOT NULL,PRIMARY KEY(scope,key));
CREATE TABLE IF NOT EXISTS mao_hybrid.events (
    id bigserial PRIMARY KEY,scope text NOT NULL,kind text NOT NULL,
    data jsonb NOT NULL,created timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS mao_events_rate ON mao_hybrid.events(scope,kind,created);
CREATE TABLE IF NOT EXISTS mao_hybrid.approvals (
    id text PRIMARY KEY,scope text NOT NULL,payload jsonb NOT NULL,
    expires timestamptz NOT NULL,approved boolean NOT NULL DEFAULT false);
INSERT INTO mao_hybrid.schema_versions(version) VALUES(1) ON CONFLICT DO NOTHING;
