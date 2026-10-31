ALTER TABLE mao_hybrid.turns ADD COLUMN IF NOT EXISTS policy_settings jsonb NOT NULL DEFAULT '{}';
ALTER TABLE mao_hybrid.preference_evidence ADD COLUMN IF NOT EXISTS feedback_event_id uuid;
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='mao_preference_feedback_source') THEN
  ALTER TABLE mao_hybrid.preference_evidence ADD CONSTRAINT mao_preference_feedback_source
   FOREIGN KEY(scope,feedback_event_id) REFERENCES mao_hybrid.interaction_events(scope,id);
 END IF;
END $$;
CREATE TABLE IF NOT EXISTS mao_hybrid.observation_receipts (
 scope text NOT NULL,event_id uuid NOT NULL,PRIMARY KEY(scope,event_id),
 FOREIGN KEY(scope,event_id) REFERENCES mao_hybrid.interaction_events(scope,id));
CREATE TABLE IF NOT EXISTS mao_hybrid.real_feedback (
 scope text NOT NULL,event_id uuid NOT NULL,target_event uuid NOT NULL,episode_id uuid NOT NULL,
 policy_revision integer NOT NULL,positive boolean NOT NULL,
 PRIMARY KEY(scope,event_id),FOREIGN KEY(scope,event_id) REFERENCES mao_hybrid.interaction_events(scope,id),
 FOREIGN KEY(scope,target_event) REFERENCES mao_hybrid.interaction_events(scope,id),
 FOREIGN KEY(scope,episode_id) REFERENCES mao_hybrid.episodes(scope,id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS mao_hybrid.lessons (
 scope text NOT NULL,id uuid NOT NULL,episode_id uuid NOT NULL,
 event_id uuid NOT NULL,dimension text NOT NULL,choice text NOT NULL,
 status text NOT NULL DEFAULT 'candidate' CHECK(status IN ('candidate','tested','retired')),
 PRIMARY KEY(scope,id),UNIQUE(scope,episode_id,dimension,choice),
 FOREIGN KEY(scope,episode_id) REFERENCES mao_hybrid.episodes(scope,id) ON DELETE CASCADE,
 FOREIGN KEY(scope,event_id) REFERENCES mao_hybrid.interaction_events(scope,id));
CREATE TABLE IF NOT EXISTS mao_hybrid.policy_versions (
 scope text NOT NULL,revision integer NOT NULL,preference_id uuid,
 settings jsonb NOT NULL,status text NOT NULL DEFAULT 'candidate'
 CHECK(status IN ('candidate','trial','active','retired','rejected')),
 budget integer NOT NULL DEFAULT 20 CHECK(budget>=0), created timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(scope,revision),FOREIGN KEY(scope,preference_id) REFERENCES mao_hybrid.character_preferences(scope,id) ON DELETE CASCADE);
DROP INDEX IF EXISTS mao_hybrid.mao_one_active_policy;
CREATE UNIQUE INDEX IF NOT EXISTS mao_one_active_preference_policy ON mao_hybrid.policy_versions(scope,preference_id) WHERE status='active';
CREATE TABLE IF NOT EXISTS mao_hybrid.evaluation_runs (
 scope text NOT NULL,id uuid NOT NULL,policy_revision integer NOT NULL,
 suite_digest text NOT NULL,split text NOT NULL CHECK(split IN ('development','held_out','real_trial')),
 samples integer NOT NULL CHECK(samples>0),baseline_score float8 NOT NULL,candidate_score float8 NOT NULL,
 hard_failures integer NOT NULL CHECK(hard_failures>=0),created timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(scope,id),FOREIGN KEY(scope,policy_revision) REFERENCES mao_hybrid.policy_versions(scope,revision) ON DELETE CASCADE);
CREATE OR REPLACE FUNCTION mao_hybrid.check_memory_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM mao_hybrid.knowledge_items k JOIN mao_hybrid.interaction_events e
   ON e.scope=k.scope AND e.room_id=k.room_id AND e.actor_id=k.actor_id AND e.visibility=k.visibility
   WHERE k.scope=NEW.scope AND k.id=NEW.item_id AND e.id=NEW.event_id AND NOT e.deleted) THEN
  RAISE EXCEPTION 'Memory evidence scope mismatch or deleted source';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS mao_memory_evidence_guard ON mao_hybrid.memory_evidence;
CREATE TRIGGER mao_memory_evidence_guard BEFORE INSERT OR UPDATE ON mao_hybrid.memory_evidence
 FOR EACH ROW EXECUTE FUNCTION mao_hybrid.check_memory_evidence();
CREATE OR REPLACE FUNCTION mao_hybrid.check_preference_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM mao_hybrid.character_preferences p JOIN mao_hybrid.interaction_events e
   ON e.scope=p.scope AND e.room_id=p.room_id AND e.actor_id=p.actor_id
   JOIN mao_hybrid.episodes x ON x.scope=e.scope AND x.room_id=e.room_id AND x.actor_id=e.actor_id
   AND x.visibility=e.visibility WHERE p.scope=NEW.scope AND p.id=NEW.preference_id
   AND e.id=NEW.event_id AND x.id=NEW.episode_id AND NOT e.deleted) THEN
  RAISE EXCEPTION 'Preference evidence scope mismatch or deleted source';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS mao_preference_evidence_guard ON mao_hybrid.preference_evidence;
CREATE TRIGGER mao_preference_evidence_guard BEFORE INSERT OR UPDATE ON mao_hybrid.preference_evidence
 FOR EACH ROW EXECUTE FUNCTION mao_hybrid.check_preference_evidence();
CREATE OR REPLACE FUNCTION mao_hybrid.check_real_feedback() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(
   SELECT 1 FROM mao_hybrid.interaction_events f
   JOIN mao_hybrid.interaction_events e ON e.scope=f.scope AND e.room_id=f.room_id AND e.actor_id=f.actor_id
   JOIN mao_hybrid.turns t ON t.scope=e.scope AND t.event_id=e.id
   JOIN mao_hybrid.episode_events p ON p.scope=e.scope AND p.event_id=e.id
   WHERE f.scope=NEW.scope AND f.id=NEW.event_id AND e.id=NEW.target_event AND p.episode_id=NEW.episode_id
   AND f.kind='input' AND e.kind='input' AND NOT f.synthetic AND NOT e.synthetic AND NOT f.deleted AND NOT e.deleted
   AND f.visibility='private' AND e.visibility='private' AND f.recorded_at>e.recorded_at
   AND t.policy_revision=NEW.policy_revision AND t.status='completed'
   AND EXISTS(SELECT 1 FROM mao_hybrid.delivery_segments d WHERE d.scope=t.scope AND d.turn_id=t.id AND d.status='completed')
 ) THEN
  RAISE EXCEPTION 'Feedback must reference an earlier delivered turn of the same actor and scope';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS mao_real_feedback_guard ON mao_hybrid.real_feedback;
CREATE TRIGGER mao_real_feedback_guard BEFORE INSERT OR UPDATE ON mao_hybrid.real_feedback
 FOR EACH ROW EXECUTE FUNCTION mao_hybrid.check_real_feedback();
INSERT INTO mao_hybrid.schema_versions(version) VALUES(9) ON CONFLICT DO NOTHING;
