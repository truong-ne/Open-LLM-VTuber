import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import mao_2048


class PreviewTelemetryTests(unittest.TestCase):
    def test_windows_reader_contention_does_not_abort_game(self):
        with tempfile.TemporaryDirectory() as directory:
            status = Path(directory) / "status.json"
            with (
                patch.object(mao_2048, "STATUS", status),
                patch.object(Path, "replace", side_effect=PermissionError) as replace,
                patch.object(mao_2048.time, "sleep"),
            ):
                self.assertFalse(mao_2048.publish(phase="playing", score=4))
                self.assertEqual(replace.call_count, 10)

    def test_successful_telemetry_contains_real_source_and_timestamp(self):
        import json

        with tempfile.TemporaryDirectory() as directory:
            status = Path(directory) / "status.json"
            with patch.object(mao_2048, "STATUS", status):
                self.assertTrue(mao_2048.publish(phase="playing", score=4))
            value = json.loads(status.read_text(encoding="utf-8"))
            self.assertEqual(value["source"], "https://2048game.com/")
            self.assertEqual(value["score"], 4)
            self.assertGreater(value["updated_at"], 0)
