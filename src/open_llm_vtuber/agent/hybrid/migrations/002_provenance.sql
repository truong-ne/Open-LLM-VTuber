ALTER TABLE mao_hybrid.memories ADD COLUMN IF NOT EXISTS public_alias text;
ALTER TABLE mao_hybrid.memories ADD COLUMN IF NOT EXISTS alias_normalized text;
ALTER TABLE mao_hybrid.memories ADD COLUMN IF NOT EXISTS evidence text;
CREATE INDEX IF NOT EXISTS mao_memory_alias ON mao_hybrid.memories(scope,alias_normalized);
INSERT INTO mao_hybrid.schema_versions(version) VALUES(2) ON CONFLICT DO NOTHING;
