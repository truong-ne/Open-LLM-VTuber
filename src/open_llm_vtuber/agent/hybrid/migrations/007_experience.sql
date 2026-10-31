CREATE TABLE IF NOT EXISTS mao_hybrid.episodes (
 scope text NOT NULL,id uuid NOT NULL,room_id text NOT NULL,actor_id text NOT NULL,
 visibility text NOT NULL CHECK(visibility IN ('private','public','test')),session_id text NOT NULL,
 topic text NOT NULL DEFAULT '', outcome text NOT NULL DEFAULT 'unknown',
 created timestamptz NOT NULL DEFAULT now(),updated timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(scope,id), FOREIGN KEY(scope,room_id) REFERENCES mao_hybrid.rooms(scope,id),
 FOREIGN KEY(scope,actor_id) REFERENCES mao_hybrid.actors(scope,id));
CREATE TABLE IF NOT EXISTS mao_hybrid.episode_events (
 scope text NOT NULL,episode_id uuid NOT NULL,event_id uuid NOT NULL,
 PRIMARY KEY(scope,event_id),
 FOREIGN KEY(scope,episode_id) REFERENCES mao_hybrid.episodes(scope,id) ON DELETE CASCADE,
 FOREIGN KEY(scope,event_id) REFERENCES mao_hybrid.interaction_events(scope,id));
CREATE TABLE IF NOT EXISTS mao_hybrid.knowledge_items (
 scope text NOT NULL,id bigserial NOT NULL,room_id text NOT NULL,actor_id text NOT NULL,
 claim_type text NOT NULL CHECK(claim_type IN ('user_claim','user_preference','fiction','shared_memory','lesson_candidate')),
 visibility text NOT NULL CHECK(visibility IN ('private','public','test')),
 item_key text, content text NOT NULL CHECK(length(content)<=4000),
 embedding vector(1024),embedding_model text,
 status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','superseded')),
 revision integer NOT NULL DEFAULT 1,valid_from timestamptz NOT NULL DEFAULT now(),
 valid_until timestamptz,created timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(scope,id),FOREIGN KEY(scope,room_id) REFERENCES mao_hybrid.rooms(scope,id),
 FOREIGN KEY(scope,actor_id) REFERENCES mao_hybrid.actors(scope,id));
CREATE TABLE IF NOT EXISTS mao_hybrid.memory_evidence (
 scope text NOT NULL,item_id bigint NOT NULL,event_id uuid NOT NULL,
 PRIMARY KEY(scope,item_id,event_id),
 FOREIGN KEY(scope,item_id) REFERENCES mao_hybrid.knowledge_items(scope,id) ON DELETE CASCADE,
 FOREIGN KEY(scope,event_id) REFERENCES mao_hybrid.interaction_events(scope,id));
CREATE TABLE IF NOT EXISTS mao_hybrid.open_threads (
 scope text NOT NULL,id uuid NOT NULL,room_id text NOT NULL,actor_id text NOT NULL,
 event_id uuid NOT NULL,topic text NOT NULL CHECK(length(topic)<=500),
 status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),
 expires timestamptz NOT NULL DEFAULT now()+interval '7 days',revision integer NOT NULL DEFAULT 1,
 PRIMARY KEY(scope,id),FOREIGN KEY(scope,room_id,event_id) REFERENCES mao_hybrid.interaction_events(scope,room_id,id));
CREATE TABLE IF NOT EXISTS mao_hybrid.activities (
 scope text NOT NULL,id uuid NOT NULL,room_id text NOT NULL,actor_id text NOT NULL,
 source_event uuid NOT NULL,kind text NOT NULL CHECK(kind='shared_story'),
 status text NOT NULL DEFAULT 'accepted' CHECK(status IN ('accepted','running','completed','failed','unknown')),
 revision integer NOT NULL DEFAULT 1,canon jsonb NOT NULL DEFAULT '[]',
 expires timestamptz NOT NULL DEFAULT now()+interval '7 days',
 PRIMARY KEY(scope,id),FOREIGN KEY(scope,room_id,source_event) REFERENCES mao_hybrid.interaction_events(scope,room_id,id));
CREATE TABLE IF NOT EXISTS mao_hybrid.activity_actions (
 scope text NOT NULL,activity_id uuid NOT NULL,action_id uuid NOT NULL,
 result jsonb NOT NULL,PRIMARY KEY(scope,activity_id,action_id),
 FOREIGN KEY(scope,activity_id) REFERENCES mao_hybrid.activities(scope,id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS mao_hybrid.activity_evidence (
 scope text NOT NULL,activity_id uuid NOT NULL,event_id uuid NOT NULL,
 PRIMARY KEY(scope,activity_id,event_id),
 FOREIGN KEY(scope,activity_id) REFERENCES mao_hybrid.activities(scope,id) ON DELETE CASCADE,
 FOREIGN KEY(scope,event_id) REFERENCES mao_hybrid.interaction_events(scope,id));
CREATE INDEX IF NOT EXISTS mao_knowledge_scope ON mao_hybrid.knowledge_items(scope,room_id,actor_id,status);
INSERT INTO mao_hybrid.schema_versions(version) VALUES(7) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS mao_hybrid.dialogue_focus (
 scope text NOT NULL,room_id text NOT NULL,actor_id text NOT NULL,visibility text NOT NULL,
 source_event uuid NOT NULL,topic text NOT NULL,question text NOT NULL DEFAULT '',repair boolean NOT NULL DEFAULT false,
 revision bigint NOT NULL DEFAULT 1,expires timestamptz NOT NULL DEFAULT now()+interval '10 minutes',
 PRIMARY KEY(scope,room_id,actor_id,visibility),
 FOREIGN KEY(scope,source_event) REFERENCES mao_hybrid.interaction_events(scope,id) ON DELETE CASCADE
);
