import unittest

from src.open_llm_vtuber.agent.hybrid.game2048 import (
    board_from_tiles,
    choose,
    move,
    promotion,
    verified_transition,
)


class GameRulesTests(unittest.TestCase):
    def test_each_tile_merges_once_and_score_matches(self):
        board = (2, 2, 2, 2) + (0,) * 12
        after, gain = move(board, "left")
        self.assertEqual(after[:4], (4, 4, 0, 0))
        self.assertEqual(gain, 8)
        self.assertEqual(move(board, "right")[0][:4], (0, 0, 4, 4))
        column = (2, 0, 0, 0, 2, 0, 0, 0, 4, 0, 0, 0, 4, 0, 0, 0)
        down, gain = move(column, "down")
        self.assertEqual([down[i] for i in (0, 4, 8, 12)], [0, 0, 4, 8])
        self.assertEqual(gain, 12)

    def test_only_one_real_spawn_and_exact_score_gain_are_accepted(self):
        before = (2, 2, 0, 0) + (0,) * 12
        predicted, gain = move(before, "left")
        after = list(predicted)
        after[15] = 2
        self.assertTrue(verified_transition(before, tuple(after), "left", 0, gain))
        self.assertFalse(verified_transition(before, tuple(after), "left", 0, gain + 4))
        after[10] = 4
        self.assertFalse(verified_transition(before, tuple(after), "left", 0, gain))
        self.assertFalse(verified_transition(predicted, predicted, "left", 0, 0))

    def test_visible_tiles_are_validated_and_transient_merged_elements_are_deduplicated(
        self,
    ):
        board = board_from_tiles(
            [
                {"classes": "tile tile-position-1-1", "value": "2"},
                {"classes": "tile tile-position-1-1 tile-merged", "value": "4"},
                {"classes": "tile tile-position-4-4", "value": "2"},
            ]
        )
        self.assertEqual(board[0], 4)
        self.assertEqual(board[-1], 2)
        with self.assertRaises(ValueError):
            board_from_tiles([{"classes": "tile-position-9-1", "value": "2"}])
        with self.assertRaises(ValueError):
            board_from_tiles([{"classes": "tile-position-1-1", "value": "3"}])

    def test_planner_uses_only_productive_legal_arrows(self):
        board = (2, 2, 0, 0) + (0,) * 12
        for policy in ("merge", "corner"):
            direction = choose(board, policy)
            self.assertNotEqual(move(board, direction)[0], board)
        full = (2, 4, 2, 4, 4, 2, 4, 2, 2, 4, 2, 4, 4, 2, 4, 2)
        self.assertIsNone(choose(full, "corner"))
        with self.assertRaises(ValueError):
            choose(board, "page-supplied-instructions")

    def test_learning_gate_requires_real_verified_games_with_matching_budgets(self):
        def run(policy, score):
            return {
                "policy": policy,
                "score": score,
                "max_moves": 250,
                "outcome": "move_budget",
                "verified": True,
            }

        history = [run("merge", 100), run("corner", 300)] * 2
        self.assertEqual(promotion(history, "merge", 250)[0], "merge")
        history += [run("merge", 100), run("corner", 300)]
        self.assertEqual(promotion(history, "merge", 250)[0], "corner")
        history[-1]["verified"] = False
        self.assertEqual(promotion(history, "merge", 250)[0], "merge")
        history[-1]["verified"] = True
        history[-1]["max_moves"] = 500
        self.assertEqual(promotion(history, "merge", 250)[0], "merge")
