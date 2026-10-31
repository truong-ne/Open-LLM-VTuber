CREATE TABLE IF NOT EXISTS mao_hybrid.character_preferences (
 scope text NOT NULL,id uuid NOT NULL,room_id text NOT NULL,actor_id text NOT NULL,
 dimension text NOT NULL CHECK(dimension IN ('verbosity','initiative','humor','examples')),
 choice text NOT NULL CHECK(choice IN ('brief','detailed','wait','offer','gentle','playful','concrete','abstract')),
 status text NOT NULL DEFAULT 'provisional' CHECK(status IN ('provisional','eligible','trial','stable','retired','locked')),
 revision integer NOT NULL DEFAULT 1, created timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(scope,id),UNIQUE(scope,room_id,actor_id,dimension,choice),
 FOREIGN KEY(scope,room_id) REFERENCES mao_hybrid.rooms(scope,id));
CREATE TABLE IF NOT EXISTS mao_hybrid.preference_evidence (
 scope text NOT NULL,preference_id uuid NOT NULL,event_id uuid NOT NULL,
 episode_id uuid NOT NULL,supports boolean NOT NULL,
 PRIMARY KEY(scope,preference_id,episode_id),
 FOREIGN KEY(scope,preference_id) REFERENCES mao_hybrid.character_preferences(scope,id) ON DELETE CASCADE,
 FOREIGN KEY(scope,event_id) REFERENCES mao_hybrid.interaction_events(scope,id),
 FOREIGN KEY(scope,episode_id) REFERENCES mao_hybrid.episodes(scope,id) ON DELETE CASCADE);
INSERT INTO mao_hybrid.schema_versions(version) VALUES(8) ON CONFLICT DO NOTHING;
