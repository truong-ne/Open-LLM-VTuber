CREATE TABLE IF NOT EXISTS mao_hybrid.rooms (
 scope text NOT NULL, id text NOT NULL, revision bigint NOT NULL DEFAULT 0,
 PRIMARY KEY(scope,id));
CREATE TABLE IF NOT EXISTS mao_hybrid.actors (
 scope text NOT NULL, id text NOT NULL, provider text NOT NULL,
 PRIMARY KEY(scope,id));
CREATE TABLE IF NOT EXISTS mao_hybrid.interaction_events (
 scope text NOT NULL, id uuid NOT NULL, schema_version integer NOT NULL DEFAULT 1,
 room_id text NOT NULL, actor_id text NOT NULL, session_id text NOT NULL,
 kind text NOT NULL, visibility text NOT NULL CHECK(visibility IN ('private','public','test')),
 source_key text, content text CHECK(length(content)<=16000),
 deleted boolean NOT NULL DEFAULT false, synthetic boolean NOT NULL DEFAULT false,
 occurred_at timestamptz NOT NULL DEFAULT now(), recorded_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(scope,id), UNIQUE(scope,room_id,actor_id,source_key),
 UNIQUE(scope,room_id,id),
 FOREIGN KEY(scope,room_id) REFERENCES mao_hybrid.rooms(scope,id),
 FOREIGN KEY(scope,actor_id) REFERENCES mao_hybrid.actors(scope,id),
 CHECK(NOT deleted OR content IS NULL));
CREATE TABLE IF NOT EXISTS mao_hybrid.turns (
 scope text NOT NULL, id uuid NOT NULL, event_id uuid NOT NULL, room_id text NOT NULL,
 actor_id text NOT NULL, epoch uuid NOT NULL, status text NOT NULL DEFAULT 'accepted'
 CHECK(status IN ('accepted','running','completed','interrupted','unknown','failed','rejected')),
 persona_revision integer, policy_revision integer NOT NULL DEFAULT 0,
 metrics jsonb NOT NULL DEFAULT '{}', created timestamptz NOT NULL DEFAULT now(),
 updated timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(scope,id), UNIQUE(scope,event_id),
 UNIQUE(scope,id,epoch),
 FOREIGN KEY(scope,room_id,event_id) REFERENCES mao_hybrid.interaction_events(scope,room_id,id));
ALTER TABLE mao_hybrid.turns ADD COLUMN IF NOT EXISTS modality text NOT NULL DEFAULT 'text' CHECK(modality IN ('text','voice'));
ALTER TABLE mao_hybrid.turns ADD COLUMN IF NOT EXISTS phase text NOT NULL DEFAULT 'first_use' CHECK(phase IN ('first_use','warm'));
CREATE TABLE IF NOT EXISTS mao_hybrid.delivery_segments (
 scope text NOT NULL, turn_id uuid NOT NULL, epoch uuid NOT NULL, id uuid NOT NULL,
 content text CHECK(length(content)<=4000), status text NOT NULL DEFAULT 'generated'
 CHECK(status IN ('generated','sent','started','completed','failed','interrupted','unknown')),
 PRIMARY KEY(scope,turn_id,id),
 FOREIGN KEY(scope,turn_id,epoch) REFERENCES mao_hybrid.turns(scope,id,epoch) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS mao_hybrid.interaction_outbox (
 scope text NOT NULL, event_id uuid NOT NULL, status text NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','processed','failed')), attempts integer NOT NULL DEFAULT 0,
 updated timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(scope,event_id),
 FOREIGN KEY(scope,event_id) REFERENCES mao_hybrid.interaction_events(scope,id) ON DELETE CASCADE);
CREATE INDEX IF NOT EXISTS mao_outbox_pending ON mao_hybrid.interaction_outbox(status,updated);
ALTER TABLE mao_hybrid.interaction_events ADD COLUMN IF NOT EXISTS raw_expired boolean NOT NULL DEFAULT false;
ALTER TABLE mao_hybrid.delivery_segments ADD COLUMN IF NOT EXISTS ordinal integer NOT NULL DEFAULT 0 CHECK(ordinal>=0);
CREATE INDEX IF NOT EXISTS mao_events_room_time ON mao_hybrid.interaction_events(scope,room_id,recorded_at);
INSERT INTO mao_hybrid.schema_versions(version) VALUES(6) ON CONFLICT DO NOTHING;
