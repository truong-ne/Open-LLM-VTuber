import os
from pathlib import Path
import unittest
from unittest.mock import patch

from src.open_llm_vtuber.config_manager import read_yaml, validate_config
from src.open_llm_vtuber.runtime_profile import apply_profile, effective_summary
from src.open_llm_vtuber.testing import assert_test_database

ROOT = Path(__file__).resolve().parents[1]


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.document = read_yaml(str(ROOT / "conf.yaml"))

    def test_local_disables_enabled_features_without_mutating_config(self):
        document = apply_profile(self.document, "live")
        basic = document["character_config"]["agent_config"]["agent_settings"][
            "basic_memory_agent"
        ]
        basic["hybrid"].update(learning_enabled=True, exploration_enabled=True)
        basic["hybrid"]["computer"]["enabled"] = True
        document["live_config"] = {
            "active_platform": "youtube",
            "youtube_live": {"channel": "synthetic"},
        }
        overlay = apply_profile(document, "local_companion")
        self.assertTrue(basic["hybrid"]["learning_enabled"])
        with patch.dict(os.environ, {"MAO_RUNTIME_PROFILE": "local_companion"}):
            summary = effective_summary(validate_config(overlay))
        self.assertFalse(summary["flags"]["learning"])
        self.assertFalse(summary["flags"]["computer"])
        self.assertEqual(summary["platform"], "local")
        self.assertEqual(overlay["live_config"]["youtube_live"]["channel"], "")

    def test_test_profile_survives_character_reload(self):
        with patch.dict(os.environ, {"MAO_RUNTIME_PROFILE": "test"}):
            config = validate_config(self.document)
            again = validate_config(config.model_dump())
        hybrid = (
            again.character_config.agent_config.agent_settings.basic_memory_agent.hybrid
        )
        self.assertEqual(hybrid.database_url_env, "MAO_TEST_DATABASE_URL")
        self.assertEqual(hybrid.persona_source, "config")
        self.assertEqual(again.system_config.port, 12394)
        self.assertEqual(again.character_config.conf_uid, "mao_synthetic_test")

    def test_summary_excludes_credentials_and_persona(self):
        import json

        document = apply_profile(self.document, "live")
        document["character_config"]["persona_prompt"] = "PRIVATE_SENTINEL"
        with patch.dict(os.environ, {"MAO_RUNTIME_PROFILE": "live"}):
            summary = effective_summary(validate_config(document))
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(summary))
        self.assertNotIn("api_key", json.dumps(summary))

    def test_configured_non_basic_agent_still_has_safe_startup_summary(self):
        document = apply_profile(self.document, "live")
        document["character_config"]["persona_prompt"] = "Synthetic non-basic agent."
        agent = document["character_config"]["agent_config"]
        agent["conversation_agent_choice"] = "letta_agent"
        agent["agent_settings"]["basic_memory_agent"] = None
        with patch.dict(os.environ, {"MAO_RUNTIME_PROFILE": "live"}):
            summary = effective_summary(validate_config(document))
        self.assertEqual(summary["agent"], "letta_agent")
        self.assertEqual(summary["flags"], {})


class DatabaseIsolationTests(unittest.TestCase):
    def test_role_password_hostname_alias_does_not_hide_same_database(self):
        with self.assertRaises(ValueError):
            assert_test_database(
                "postgresql://test:secret@localhost:55432/mao_test",
                ["postgresql://owner:other@127.0.0.1:55432/mao_test"],
            )

    def test_refuses_production_name_and_implicit_defaults(self):
        for dsn in (
            "postgresql://test:secret@localhost:55432/mao",
            "dbname=mao_test",
            "",
        ):
            with self.subTest(dsn=bool(dsn)), self.assertRaises(ValueError) as error:
                assert_test_database(dsn)
            self.assertNotIn("secret", str(error.exception))

    def test_separate_database_is_accepted(self):
        assert_test_database(
            "postgresql://test:secret@localhost:55433/mao_test",
            ["postgresql://owner:other@127.0.0.1:55432/mao"],
        )

    def test_direct_integration_run_cannot_fall_back_to_production(self):
        from src.open_llm_vtuber.agent.hybrid.config import HybridConfig
        from src.open_llm_vtuber.agent.hybrid.store import resolve_dsn

        with patch.dict(
            os.environ,
            {
                "MAO_TEST_POSTGRES": "1",
                "MAO_DATABASE_URL": "postgresql://a:b@localhost:55432/mao",
            },
        ):
            with self.assertRaises(ValueError):
                resolve_dsn(HybridConfig())


class BaselineProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_content_marks_first_token_and_stream_is_preserved(self):
        import time
        from scripts.mao_baseline import TokenProbe

        class Model:
            async def chat_completion(self):
                for event in (
                    {"type": "tool_call"},
                    {"type": "text_delta", "text": "synthetic"},
                    " response",
                ):
                    yield event

        probe = TokenProbe(Model())
        probe.marks, probe.started = {}, time.monotonic()
        events = [event async for event in probe.chat_completion()]
        self.assertEqual(len(events), 3)
        self.assertGreaterEqual(probe.marks["first_token_ms"], 0)
        self.assertEqual(set(probe.marks), {"first_token_ms"})
