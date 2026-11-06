ALTER TABLE mao_hybrid.dialogue_focus ADD COLUMN IF NOT EXISTS topic_event uuid;
ALTER TABLE mao_hybrid.dialogue_focus ADD COLUMN IF NOT EXISTS quiet_event uuid;
ALTER TABLE mao_hybrid.dialogue_focus ADD COLUMN IF NOT EXISTS quiet_until timestamptz;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='mao_focus_topic_source' AND conrelid='mao_hybrid.dialogue_focus'::regclass) THEN
  ALTER TABLE mao_hybrid.dialogue_focus ADD CONSTRAINT mao_focus_topic_source
   FOREIGN KEY(scope,topic_event) REFERENCES mao_hybrid.interaction_events(scope,id) ON DELETE CASCADE;
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='mao_focus_quiet_source' AND conrelid='mao_hybrid.dialogue_focus'::regclass) THEN
  ALTER TABLE mao_hybrid.dialogue_focus ADD CONSTRAINT mao_focus_quiet_source
   FOREIGN KEY(scope,quiet_event) REFERENCES mao_hybrid.interaction_events(scope,id) ON DELETE CASCADE;
 END IF;
END $$;
INSERT INTO mao_hybrid.schema_versions(version) VALUES(10) ON CONFLICT DO NOTHING;
