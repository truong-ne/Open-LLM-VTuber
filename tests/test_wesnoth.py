import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import time
import unittest
from unittest.mock import AsyncMock, patch

from src.open_llm_vtuber.agent.hybrid.contracts import validate
from src.open_llm_vtuber.agent.hybrid.runtime import HybridRuntime, TOOL
from src.open_llm_vtuber.agent.hybrid.executor import HybridExecutor
from src.open_llm_vtuber.games.wesnoth import WesnothBridge, write_json, read_json
from src.open_llm_vtuber.interaction.ingress import (
    sign_host_proposal,
    verify_host_proposal,
)
from src.open_llm_vtuber.runtime_profile import apply_profile


class WesnothTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.bridge = WesnothBridge(self.directory)
        self.session = "a" * 32
        self.state = {
            "session": self.session,
            "request_id": "1:1:1",
            "expires_at": time.time() + 60,
            "actions": [{"id": "a0", "kind": "end_turn"}, {"id": "a1", "kind": "move"}],
        }

    def publish(self):
        write_json(self.directory / "state.json", self.state)

    def choose(self, action="a1"):
        return self.bridge.choose(self.session, "1:1:1", action)

    def test_not_running_and_expired(self):
        self.assertEqual(self.bridge.observe()["status"], "not_running")
        self.state["expires_at"] = time.time() - 1
        self.publish()
        self.assertEqual(self.bridge.observe()["status"], "expired")
        with self.assertRaises(PermissionError):
            self.choose()
        self.assertFalse((self.directory / "command.json").exists())

    def test_only_game_supplied_actions_can_be_selected(self):
        self.publish()
        with self.assertRaises(ValueError):
            self.choose("a999")
        self.assertEqual(self.choose()["status"], "submitted")
        self.assertEqual(read_json(self.directory / "command.json")["action_id"], "a1")

    def test_duplicate_is_idempotent_and_different_choice_rejected(self):
        self.publish()
        self.choose()
        self.assertEqual(self.choose()["status"], "already_submitted")
        with self.assertRaises(PermissionError):
            self.choose("a0")

    def test_concurrent_choices_have_one_winner(self):
        self.publish()

        def attempt(action):
            try:
                return self.choose(action)["status"]
            except PermissionError:
                return "rejected"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, ["a0", "a1"]))
        self.assertCountEqual(results, ["submitted", "rejected"])

    def test_previous_session_and_turn_rejected(self):
        self.publish()
        for session, request in [("b" * 32, "1:1:1"), (self.session, "2:1:1")]:
            with self.assertRaises(PermissionError):
                self.bridge.choose(session, request, "a0")

    def test_retry_recovers_command_write_failure_without_changing_choice(self):
        self.publish()
        with patch(
            "src.open_llm_vtuber.games.wesnoth.write_json",
            side_effect=OSError("disk temporarily unavailable"),
        ):
            with self.assertRaises(OSError):
                self.choose()
        self.assertEqual(self.choose()["status"], "already_submitted")
        self.assertEqual(read_json(self.directory / "command.json")["action_id"], "a1")

    async def test_game_failure_is_not_reported_as_success(self):
        self.publish()
        arguments = {
            "action": "choose",
            "session": self.session,
            "request_id": "1:1:1",
            "action_id": "a1",
        }
        write_json(
            self.directory / "result.json",
            {**arguments, "status": "failed", "confirmed": False},
        )
        result = await self.bridge.execute(arguments, wait_seconds=1)
        self.assertFalse(result["confirmed"])
        self.assertEqual(result["status"], "failed")

    def test_arbitrary_code_paths_and_fields_rejected(self):
        for data in [
            {"action": "choose"},
            {"action": "observe", "action_id": "a0"},
            {"action": "observe", "code": "os.execute('anything')"},
            {
                "action": "choose",
                "session": "../other",
                "request_id": "1:1:1",
                "action_id": "a0",
            },
        ]:
            with self.assertRaises(ValueError):
                validate("wesnoth", data)

    async def test_submission_does_not_claim_completion(self):
        self.publish()
        result = await self.bridge.execute(
            {
                "action": "choose",
                "session": self.session,
                "request_id": "1:1:1",
                "action_id": "a1",
            },
            wait_seconds=0,
        )
        self.assertFalse(result["confirmed"])

    async def test_only_matching_game_ack_confirms_completion(self):
        self.publish()
        arguments = {
            "action": "choose",
            "session": self.session,
            "request_id": "1:1:1",
            "action_id": "a1",
        }
        write_json(
            self.directory / "result.json",
            {
                "session": "b" * 32,
                "request_id": "1:1:1",
                "action_id": "a1",
                "confirmed": True,
            },
        )

        async def acknowledge():
            await asyncio.sleep(0.15)
            write_json(
                self.directory / "result.json",
                {**arguments, "status": "completed", "confirmed": True},
            )

        task = asyncio.create_task(acknowledge())
        result = await self.bridge.execute(arguments, wait_seconds=1)
        await task
        self.assertTrue(result["confirmed"])
        self.assertEqual(result["session"], self.session)

    async def test_disabled_runtime_cannot_control_game(self):
        runtime = HybridRuntime.__new__(HybridRuntime)
        runtime.config = SimpleNamespace(wesnoth_enabled=False)
        with self.assertRaises(PermissionError):
            await runtime.dispatch("wesnoth", {"action": "observe"})

    async def test_enabled_runtime_routes_to_game_adapter(self):
        self.publish()
        runtime = HybridRuntime.__new__(HybridRuntime)
        runtime.config = SimpleNamespace(wesnoth_enabled=True)
        with patch(
            "src.open_llm_vtuber.games.wesnoth.WesnothBridge", return_value=self.bridge
        ):
            result = await runtime.dispatch("wesnoth", {"action": "observe"})
        self.assertEqual(result["request_id"], "1:1:1")

    def test_new_tool_does_not_remove_browser_actions_from_schema(self):
        actions = TOOL["input_schema"]["properties"]["data"]["properties"]["action"][
            "enum"
        ]
        self.assertTrue(
            {"click", "navigate", "vision_click", "observe", "choose"} <= set(actions)
        )

    def test_game_host_messages_require_untampered_signature(self):
        with patch(
            "src.open_llm_vtuber.interaction.ingress.key", return_value=b"a" * 32
        ):
            signed = sign_host_proposal(
                {
                    "type": "text-input",
                    "source": "mao-wesnoth",
                    "text": "Choose current game action",
                }
            )
            self.assertTrue(verify_host_proposal(signed))
            signed["text"] = "Different action"
            self.assertFalse(verify_host_proposal(signed))

    async def test_game_turn_supplies_current_choices_in_signed_prompt(self):
        from scripts.mao_wesnoth import notify_mao

        ws = SimpleNamespace(send=AsyncMock())
        state = {**self.state, "turn": 1, "side": 1, "gold": 60, "units": []}
        with patch(
            "src.open_llm_vtuber.interaction.ingress.key", return_value=b"a" * 32
        ):
            await notify_mao(ws, state)
            message = json.loads(ws.send.call_args.args[0])
            self.assertTrue(verify_host_proposal(message))
        observation = json.loads(message["text"].splitlines()[-1])
        self.assertEqual(observation["request_id"], state["request_id"])
        self.assertEqual(observation["actions"], state["actions"])
        self.assertEqual(observation["session"], state["session"])

    def test_test_profile_cannot_touch_real_game(self):
        document = {
            "character_config": {
                "agent_config": {
                    "conversation_agent_choice": "basic_memory_agent",
                    "agent_settings": {
                        "basic_memory_agent": {"hybrid": {"wesnoth_enabled": True}}
                    },
                }
            }
        }
        result = apply_profile(document, "test")
        self.assertFalse(
            result["character_config"]["agent_config"]["agent_settings"][
                "basic_memory_agent"
            ]["hybrid"]["wesnoth_enabled"]
        )
        self.assertTrue(
            document["character_config"]["agent_config"]["agent_settings"][
                "basic_memory_agent"
            ]["hybrid"]["wesnoth_enabled"]
        )

    def test_oversized_bridge_record_rejected(self):
        (self.directory / "state.json").write_text(
            json.dumps({"padding": "x" * 100_000})
        )
        with self.assertRaises(ValueError):
            self.bridge.observe()

    async def test_game_request_id_is_not_an_operator_approval(self):
        executor = HybridExecutor.__new__(HybridExecutor)
        executor.runtime = SimpleNamespace(
            dispatch=AsyncMock(return_value={"request_id": "1:1:1", "confirmed": True})
        )
        result = await executor.run_single_tool(
            "mao_hybrid", "call1", {"operation": "wesnoth", "data": {}}
        )
        self.assertIsNone(result[2]["confirmation"])

    async def test_browser_approval_is_still_exposed(self):
        executor = HybridExecutor.__new__(HybridExecutor)
        executor.runtime = SimpleNamespace(
            dispatch=AsyncMock(return_value={"request_id": "approval1"})
        )
        result = await executor.run_single_tool(
            "mao_hybrid", "call1", {"operation": "computer", "data": {}}
        )
        self.assertEqual(result[2]["confirmation"], "approval1")

    def test_atomic_write_retries_windows_sharing_violation(self):
        original = Path.replace
        attempts = []

        def replace(path, target):
            attempts.append(path)
            if len(attempts) == 1:
                raise PermissionError("sharing violation")
            return original(path, target)

        with (
            patch.object(Path, "replace", replace),
            patch("src.open_llm_vtuber.games.wesnoth.time.sleep"),
        ):
            self.publish()
        self.assertEqual(len(attempts), 2)
        self.assertEqual(read_json(self.directory / "state.json"), self.state)
        self.assertEqual(list(self.directory.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
