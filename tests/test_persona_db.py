import os
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
import uuid

from pydantic import ValidationError
from src.open_llm_vtuber.agent.hybrid.persona import (
    ProfileEdit,
    UNCONFIGURED,
    profile_prompt,
    read_profile,
    write_profile,
)
from src.open_llm_vtuber.agent.hybrid.runtime import HybridRuntime
from src.open_llm_vtuber.agent.hybrid.config import HybridConfig
from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource


def message(text):
    return BatchInput(
        texts=[TextData(source=TextSource.INPUT, content=text, from_name="Human")]
    )


class PersonaContractTests(unittest.TestCase):
    def test_blank_active_profile_is_rejected_and_no_style_is_seeded(self):
        with self.assertRaises(ValidationError):
            ProfileEdit(revision=1, status="active", prompt=" ")
        draft = ProfileEdit(revision=1, status="draft")
        self.assertEqual(draft.prompt, "")
        self.assertEqual(draft.topics, [])
        self.assertEqual(profile_prompt(draft.model_dump()), "")
        with self.assertRaises(ValidationError):
            ProfileEdit(revision=1, status="draft", approved=True)


class PersonaRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_draft_blocks_generation_and_retrieval(self):
        store = Mock()
        runtime = HybridRuntime(HybridConfig(persona_source="postgres"), store=store)
        with patch(
            "src.open_llm_vtuber.agent.hybrid.runtime.read_profile",
            return_value={"revision": 1, "status": "draft", "prompt": ""},
        ):
            await runtime.prepare(message("hello"))
        self.assertEqual(runtime.direct_reply, UNCONFIGURED)
        store.recall.assert_not_called()
        self.assertTrue(runtime.persona_changed)
        self.assertEqual(runtime.traits, {})

    async def test_database_failure_has_no_legacy_personality_fallback(self):
        runtime = HybridRuntime(
            HybridConfig(persona_source="postgres"),
            store=Mock(embedding_status="not_checked"),
        )
        with patch(
            "src.open_llm_vtuber.agent.hybrid.runtime.read_profile",
            side_effect=RuntimeError("offline"),
        ):
            await runtime.prepare(message("hello"))
        self.assertIsNone(runtime.profile)
        self.assertIn("PostgreSQL", runtime.direct_reply)
        self.assertNotIn("Malfoy", runtime.context())

    async def test_active_profile_is_reloaded_each_turn_and_can_choose_own_pronouns(
        self,
    ):
        store = Mock()
        store.get.return_value = {}
        store.recall.return_value = []
        store.embedding_status = "ready"
        runtime = HybridRuntime(HybridConfig(persona_source="postgres"), store=store)
        profiles = [
            {
                "revision": 2,
                "status": "active",
                "prompt": "Synthetic persona A; use I.",
            },
            {
                "revision": 3,
                "status": "active",
                "prompt": "Synthetic persona B; use we.",
            },
        ]
        with patch(
            "src.open_llm_vtuber.agent.hybrid.runtime.read_profile",
            side_effect=profiles,
        ):
            await runtime.prepare(message("hello"))
            self.assertIn("Synthetic persona A", runtime.context())
            await runtime.prepare(message("hello"))
            self.assertIn("Synthetic persona B", runtime.context())
        self.assertNotIn("Synthetic persona A", runtime.context())
        self.assertNotIn("thiếp", runtime.context())
        self.assertTrue(runtime.persona_changed)

    async def test_agent_cannot_reinject_yaml_persona_and_draft_never_calls_llm(self):
        from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent

        store = Mock()
        store.embedding_status = "not_checked"
        llm = Mock()
        from src.open_llm_vtuber.config_manager.tts_preprocessor import (
            TTSPreprocessorConfig,
        )

        tts_config = TTSPreprocessorConfig(
            remove_special_char=False,
            translator_config={
                "translate_audio": False,
                "translate_provider": "deeplx",
            },
        )
        avatar = SimpleNamespace(
            extract_emotion=lambda text: [],
            context_motions_for_sentence=lambda text: [],
            remove_context_motion_tags=lambda text: text,
        )
        with patch(
            "src.open_llm_vtuber.agent.hybrid.runtime.Store", return_value=store
        ):
            agent = BasicMemoryAgent(
                llm,
                "LEGACY YAML PERSONALITY",
                avatar,
                tts_preprocessor_config=tts_config,
                segment_method="regex",
                hybrid_config={"enabled": True, "persona_source": "postgres"},
            )
        agent._add_message("OLD WORKING MEMORY", "assistant")
        with patch(
            "src.open_llm_vtuber.agent.hybrid.runtime.read_profile",
            return_value={"revision": 1, "status": "draft", "prompt": ""},
        ):
            outputs = [part async for part in agent.chat(message("hello"))]
        self.assertTrue(outputs)
        llm.chat_completion.assert_not_called()
        self.assertNotIn("LEGACY YAML", agent._system_prompt())
        self.assertNotIn("OLD WORKING MEMORY", str(agent._memory))
        await agent.close()


@unittest.skipUnless(
    os.environ.get("MAO_TEST_POSTGRES") == "1", "PostgreSQL integration opt-in"
)
class PersonaDatabaseTests(unittest.TestCase):
    def setUp(self):
        from scripts.mao_hybrid import config
        from src.open_llm_vtuber.agent.hybrid.store import Store

        self.settings = config().model_copy(
            update={"scope": "test-persona-" + uuid.uuid4().hex}
        )
        self.admin = Store(
            self.settings.model_copy(
                update={"database_url_env": "MAO_DATABASE_ADMIN_URL"}
            )
        )
        self.runtime = Store(self.settings)
        with self.admin.connect() as db:
            db.execute(
                "INSERT INTO mao_hybrid.character_profiles(scope) VALUES(%s)",
                (self.settings.scope,),
            )

    def tearDown(self):
        with self.admin.connect() as db:
            db.execute(
                "DELETE FROM mao_hybrid.character_profiles WHERE scope=%s",
                (self.settings.scope,),
            )
        self.runtime.close()
        self.admin.close()

    def test_operator_updates_are_atomic_and_runtime_cannot_edit(self):
        from psycopg.errors import InsufficientPrivilege

        self.assertEqual(read_profile(self.runtime)["status"], "draft")
        active = write_profile(
            self.admin,
            {"revision": 1, "status": "active", "prompt": "Isolated test persona"},
        )
        self.assertEqual(active["revision"], 2)
        self.assertEqual(read_profile(self.runtime)["prompt"], "Isolated test persona")
        with self.assertRaises(ValueError):
            write_profile(
                self.admin, {"revision": 1, "status": "draft", "prompt": "stale"}
            )
        with self.assertRaises(InsufficientPrivilege):
            with self.runtime.connect() as db:
                db.execute(
                    "UPDATE mao_hybrid.character_profiles SET prompt='model edit' WHERE scope=%s",
                    (self.settings.scope,),
                )
        self.assertEqual(read_profile(self.runtime)["prompt"], "Isolated test persona")
