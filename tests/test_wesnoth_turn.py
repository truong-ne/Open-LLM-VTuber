import json
from types import SimpleNamespace
import time
import unittest
from unittest.mock import AsyncMock

from src.open_llm_vtuber.games.wesnoth_turn import (
    parse_choice,
    describe_result,
    play_turn,
)


class Model:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    async def chat_completion(self, messages, system, tools=None):
        self.calls.append({"tools": tools, "system": system})
        yield next(self.responses)


class WesnothTurnTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.state = {
            "status": "awaiting_action",
            "session": "a" * 32,
            "request_id": "1:1:1",
            "expires_at": time.time() + 60,
            "units": [{"id": "enemy", "hp": 38}],
            "actions": [
                {"id": "a0", "kind": "end_turn"},
                {"id": "a1", "kind": "attack"},
            ],
        }
        self.result = {
            "confirmed": True,
            "status": "completed",
            "executed": {"kind": "attack", "target": "enemy"},
            "units": [{"id": "enemy", "hp": 38}],
        }
        self.input = SimpleNamespace(
            texts=[
                SimpleNamespace(
                    content="[Lượt chơi Wesnoth]\n" + json.dumps(self.state)
                )
            ]
        )
        self.runtime = SimpleNamespace(
            dispatch=AsyncMock(side_effect=[self.state, self.result])
        )

    def test_choice_cannot_inject_extra_actions_or_code(self):
        for text in [
            '{"action_id":"a999"}',
            '{"action_id":"a1","code":"anything"}',
            '"a1"',
            "I moved already",
        ]:
            with self.assertRaises(ValueError):
                parse_choice(text, self.state["actions"])
        self.assertEqual(
            parse_choice('```json\n{"action_id":"a1"}\n```', self.state["actions"]),
            "a1",
        )

    async def test_model_plan_is_not_spoken_or_executed(self):
        model = Model(["Mao đã di chuyển và thắng rồi!", '{"action_id":"a1"}'])
        speech = await play_turn(model, "Mao persona", self.runtime, self.input)
        self.assertEqual(len(model.calls), 2)
        self.assertTrue(all(c["tools"] is None for c in model.calls))
        self.assertEqual(
            self.runtime.dispatch.await_args_list[-1].args[1]["action_id"], "a1"
        )
        self.assertIn("không gây sát thương", speech)
        self.assertNotIn("thắng", speech)

    async def test_invalid_choices_never_execute(self):
        model = Model(['{"action_id":"a999"}'] * 3)
        speech = await play_turn(model, "Mao persona", self.runtime, self.input)
        self.assertEqual(self.runtime.dispatch.await_count, 1)
        self.assertIn("chưa chọn được", speech)

    async def test_old_prompt_does_not_act_on_new_turn(self):
        self.runtime.dispatch = AsyncMock(
            return_value={**self.state, "request_id": "2:1:2"}
        )
        model = Model([])
        speech = await play_turn(model, "Mao persona", self.runtime, self.input)
        self.assertEqual(model.calls, [])
        self.assertIn("hết hạn", speech)

    async def test_unconfirmed_action_is_not_narrated_as_completed(self):
        self.runtime.dispatch = AsyncMock(
            side_effect=[self.state, {"confirmed": False, "status": "submitted"}]
        )
        speech = await play_turn(
            Model(['{"action_id":"a1"}']), "Mao persona", self.runtime, self.input
        )
        self.assertIn("chưa nhận được xác nhận", speech)

    async def test_permission_denial_does_not_reach_model(self):
        self.runtime.dispatch = AsyncMock(side_effect=PermissionError("disabled"))
        model = Model([])
        speech = await play_turn(model, "Mao persona", self.runtime, self.input)
        self.assertEqual(model.calls, [])
        self.assertIn("chưa thực hiện", speech)

    def test_damage_and_casualty_claims_use_game_evidence(self):
        damaged = {**self.result, "units": [{"id": "enemy", "hp": 20}]}
        self.assertIn("mất 18 máu", describe_result(self.state, damaged))
        self.assertIn(
            "hạ được", describe_result(self.state, {**self.result, "units": []})
        )

    def test_recruit_and_move_use_actual_result(self):
        self.assertIn(
            "lính cung, còn 46 vàng",
            describe_result(
                self.state,
                {
                    "confirmed": True,
                    "executed": {"kind": "recruit", "unit_type": "Bowman"},
                    "gold": 46,
                },
            ),
        )
        self.assertIn(
            "ô 4, 5",
            describe_result(
                self.state,
                {
                    "confirmed": True,
                    "executed": {"kind": "move", "unit": "mao"},
                    "units": [{"id": "mao", "x": 4, "y": 5}],
                },
            ),
        )
