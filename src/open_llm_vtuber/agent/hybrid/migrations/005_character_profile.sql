-- Persona is operator-owned configuration, never learned or writable by a model.
CREATE TABLE IF NOT EXISTS mao_hybrid.character_profiles (
    scope text PRIMARY KEY,
    revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
    status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','active')),
    prompt text NOT NULL DEFAULT '' CHECK(length(prompt)<=16000),
    proactive_prompt text NOT NULL DEFAULT '' CHECK(length(proactive_prompt)<=4000),
    autonomy_prompt text NOT NULL DEFAULT '' CHECK(length(autonomy_prompt)<=4000),
    topics jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(topics)='array'),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK(status='draft' OR length(trim(prompt))>0)
);
DO $$ BEGIN
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='mao_app') THEN
        REVOKE ALL ON mao_hybrid.character_profiles FROM mao_app;
        GRANT SELECT ON mao_hybrid.character_profiles TO mao_app;
    END IF;
END $$;
INSERT INTO mao_hybrid.character_profiles(scope) VALUES('mao') ON CONFLICT DO NOTHING;
INSERT INTO mao_hybrid.schema_versions(version) VALUES(5) ON CONFLICT DO NOTHING;
