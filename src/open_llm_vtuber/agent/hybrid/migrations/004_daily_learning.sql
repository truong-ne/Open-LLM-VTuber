-- Metrics contain no conversation text. Operator ratings cannot be written by mao_app.
CREATE TABLE IF NOT EXISTS mao_hybrid.learning_profiles (
    version bigserial PRIMARY KEY, scope text NOT NULL,
    proactive_max_words integer NOT NULL CHECK(proactive_max_words BETWEEN 40 AND 60),
    reason text NOT NULL, created timestamptz NOT NULL DEFAULT now(),
    UNIQUE(scope,version));
CREATE TABLE IF NOT EXISTS mao_hybrid.learning_turns (
    id text NOT NULL, scope text NOT NULL, created timestamptz NOT NULL DEFAULT now(),
    kind text NOT NULL CHECK(kind IN ('conversation','proactive','rehearsal')),
    profile_version bigint, response_hash text NOT NULL,
    metrics jsonb NOT NULL, PRIMARY KEY(scope,id),
    FOREIGN KEY(scope,profile_version) REFERENCES mao_hybrid.learning_profiles(scope,version));
CREATE INDEX IF NOT EXISTS mao_learning_turns_day ON mao_hybrid.learning_turns(scope,created);
CREATE TABLE IF NOT EXISTS mao_hybrid.learning_feedback (
    scope text NOT NULL, turn_id text NOT NULL, created timestamptz NOT NULL DEFAULT now(),
    label text NOT NULL CHECK(label IN ('useful','too_long','too_short','incorrect','unsafe')),
    PRIMARY KEY(scope,turn_id),
    FOREIGN KEY(scope,turn_id) REFERENCES mao_hybrid.learning_turns(scope,id) ON DELETE CASCADE);
CREATE INDEX IF NOT EXISTS mao_learning_feedback_day ON mao_hybrid.learning_feedback(scope,created);
CREATE TABLE IF NOT EXISTS mao_hybrid.learning_days (
    scope text NOT NULL, day date NOT NULL, report jsonb NOT NULL,
    created timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(scope,day));
INSERT INTO mao_hybrid.schema_versions(version) VALUES(4) ON CONFLICT DO NOTHING;
