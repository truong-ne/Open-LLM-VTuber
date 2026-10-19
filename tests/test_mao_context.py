import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

from scripts import configure_mao
from src.open_llm_vtuber.agent.vietnam_knowledge import PERSONA_MARKER


class MaoContextSyncTests(unittest.TestCase):
    def test_sync_only_changes_identity_and_preserves_runtime_settings(self):
        persona = (configure_mao.ROOT / configure_mao.PERSONA_PATH).read_text(
            encoding="utf-8"
        )
        original = {
            "system_config": {
                "host": "localhost",
                "tool_prompts": {"pet_action_prompt": "mao_pet_actions"},
            },
            "character_config": {
                "conf_name": "Previous Mao",
                "conf_uid": "previous-mao",
                "character_name": "Mao",
                "persona_prompt": "old context",
                "live2d_model_name": "mao_pro",
                "tts_config": {"voice": "keep-voice"},
                "agent_config": {"provider": "keep-model", "temperature": 0.42},
                "asr_config": {"provider": "keep-asr"},
                "custom": [1, 2, 3],
            },
        }
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "prompts").mkdir()
            (root / "characters").mkdir()
            (root / configure_mao.PERSONA_PATH).write_text(persona, encoding="utf-8")
            paths = [root / "conf.yaml", root / "characters/mao_live.yaml"]
            for path in paths:
                path.write_text(yaml.safe_dump(original), encoding="utf-8")
            with patch.object(configure_mao, "ROOT", root):
                configure_mao.main()
                first = [path.read_bytes() for path in paths]
                configure_mao.main()
                self.assertEqual(first, [path.read_bytes() for path in paths])
            expected = copy.deepcopy(original)
            expected["character_config"].update(
                persona_prompt=persona,
                character_name="Mao",
                conf_name="Mao VTuber — Fem Malfoy",
                conf_uid="mao_fem_malfoy_vi_003",
            )
            for path in paths:
                self.assertEqual(
                    yaml.safe_load(path.read_text(encoding="utf-8")), expected
                )
            self.assertEqual(persona.count(PERSONA_MARKER), 1)

    def test_invalid_context_is_rejected_before_config_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "prompts").mkdir()
            (root / configure_mao.PERSONA_PATH).write_text(
                "Incomplete context", encoding="utf-8"
            )
            with (
                patch.object(configure_mao, "ROOT", root),
                self.assertRaises(ValueError),
            ):
                configure_mao.main()
            self.assertFalse((root / "conf.yaml").exists())
