-- Two public aliases can say the same sentence; do not deduplicate them together.
ALTER TABLE mao_hybrid.memories DROP CONSTRAINT IF EXISTS memories_scope_kind_subject_content_hash_key;
CREATE UNIQUE INDEX IF NOT EXISTS mao_memory_claim_key ON mao_hybrid.memories
    (scope,kind,subject,(coalesce(alias_normalized,'')),content_hash);
INSERT INTO mao_hybrid.schema_versions(version) VALUES(3) ON CONFLICT DO NOTHING;
