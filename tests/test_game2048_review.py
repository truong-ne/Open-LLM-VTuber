import json
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import review_mao_game


class EvidenceReviewTests(unittest.TestCase):
    def test_short_showcase_cannot_distort_learning_comparison(self):
        history = [
            {
                "id": str(i),
                "policy": p,
                "score": score,
                "moves": 250,
                "max_moves": 250,
                "verified": True,
                "outcome": "move_budget",
            }
            for i, (p, score) in enumerate([("merge", 100), ("corner", 200)] * 3)
        ] + [
            {
                "id": "showcase",
                "policy": "corner",
                "score": 4,
                "moves": 20,
                "max_moves": 20,
                "verified": True,
                "outcome": "move_budget",
            }
        ]
        game, memory = MagicMock(), MagicMock()
        game.get.side_effect = [history, {"policy": "corner", "version": 1}]
        memory.embedding_status = "ready"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "logs").mkdir()
            with (
                patch.object(review_mao_game, "ROOT", root),
                patch.object(review_mao_game, "config"),
                patch.object(review_mao_game, "Store", side_effect=[game, memory]),
            ):
                result = review_mao_game.review_games(False)
        self.assertEqual(result["verified_runs"], 7)
        self.assertEqual(result["comparison_runs"], 6)
        self.assertEqual(result["mean_scores"], {"merge": 100, "corner": 200})
        self.assertFalse(result["quality_improvement_verified"])
        saved = json.loads(memory.remember.call_args.args[2])
        self.assertFalse(saved["hypothesis_verified"])
        self.assertEqual(memory.remember.call_args.args[3], "evaluation")
        game.close.assert_called_once()
        memory.close.assert_called_once()
