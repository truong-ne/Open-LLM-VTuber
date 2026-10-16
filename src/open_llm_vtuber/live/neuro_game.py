"""
Neuro Game API bridge.

Implements the server side of the Neuro Game SDK websocket API
(https://github.com/VedalAI/neuro-sdk/blob/main/API/SPECIFICATION.md), so games
built for Neuro-sama can be played by the Open-LLM-VTuber character.

- The game connects here (Unity/Godot SDKs read the URL from NEURO_SDK_WS_URL).
- When the game forces an action, the LLM picks one of the allowed actions with
  native tool calling; the parameters are validated against the action schema
  before being sent to the game, and failed actions are retried like Neuro does.
- Game context and chosen actions are sent to the VTuber through the proxy
  WebSocket, so the character comments on the game in its own voice.

Decisions do not wait for the character to finish talking, so the game is not
slowed down by speech.
"""

import asyncio
import json
import re
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Deque, Dict, List, Optional, Set

import websockets
from loguru import logger
from openai import AsyncOpenAI

try:
    import jsonschema
except ImportError:  # pragma: no cover - jsonschema comes with mcp
    jsonschema = None

# The spec treats results arriving after ~20 seconds as failed
ACTION_RESULT_TIMEOUT = 20.0
MAX_STATE_CHARS = 4000
_THINK_TAG = re.compile(r"<think>.*?</think>", re.S)


@dataclass
class NeuroAction:
    """An action registered by the game."""

    name: str
    description: str = ""
    schema: Optional[Dict[str, Any]] = None

    def to_openai_tool(self) -> Dict[str, Any]:
        parameters = self.schema or {"type": "object", "properties": {}}
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }


@dataclass
class ActionChoice:
    """An action picked by the LLM."""

    name: str
    data: Optional[str] = None
    thought: str = ""


@dataclass
class ActionResult:
    """The game's answer to an action."""

    success: bool
    message: str = ""


def parse_actions(raw_actions: Any) -> List[NeuroAction]:
    """Parse the `actions` list of an actions/register message, skipping bad entries."""
    actions = []
    if not isinstance(raw_actions, list):
        return actions
    for raw in raw_actions:
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
            continue
        schema = raw.get("schema")
        actions.append(
            NeuroAction(
                name=raw["name"],
                description=str(raw.get("description") or ""),
                schema=schema if isinstance(schema, dict) and schema else None,
            )
        )
    return actions


def validate_action_data(action: NeuroAction, data: Optional[str]) -> Optional[str]:
    """
    Check the LLM's parameters against the action schema.

    Returns:
        An error message for the LLM, or None if the data is valid.
    """
    if not action.schema:
        return None
    try:
        parsed = json.loads(data) if data else {}
    except json.JSONDecodeError as e:
        return f"Arguments for '{action.name}' are not valid JSON: {e}"
    if not isinstance(parsed, dict):
        return f"Arguments for '{action.name}' must be a JSON object."

    if jsonschema is not None:
        try:
            jsonschema.validate(parsed, action.schema)
        except jsonschema.ValidationError as e:
            return f"Invalid arguments for '{action.name}': {e.message}"
        except jsonschema.SchemaError:
            pass  # The game's schema itself is odd; let the game judge the data
    else:
        missing = [k for k in action.schema.get("required", []) if k not in parsed]
        if missing:
            return f"Missing required argument(s) for '{action.name}': {', '.join(missing)}"
    return None


def build_decision_messages(
    persona: str,
    game: str,
    context: List[str],
    state: Optional[str],
    query: str,
    last_error: Optional[str],
) -> List[Dict[str, str]]:
    """Build the chat messages asking the LLM to pick a game action."""
    system = (
        f"{persona.strip()}\n\n"
        f"You are playing the game '{game}'. Pick what to do by calling one of the "
        "provided functions. Arguments must follow the function's parameter schema. "
        "Play to win, but stay in character."
    )
    parts = []
    if context:
        parts.append("Recent game events:\n" + "\n".join(f"- {c}" for c in context))
    if state:
        parts.append("Current game state:\n" + state[:MAX_STATE_CHARS])
    parts.append("Task: " + (query or "Decide what to do next."))
    if last_error:
        parts.append(f"Your previous attempt failed: {last_error}\nTry again.")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def describe_choice(
    game: str, query: str, choice: ActionChoice, result_message: str
) -> str:
    """Text sent to the VTuber so it comments on the action it just took."""
    args = (
        f" with {choice.data}"
        if choice.data and choice.data.strip() not in ("", "{}")
        else ""
    )
    lines = [f"[Game: {game}] {query}".strip(), f"You chose '{choice.name}'{args}."]
    if choice.thought:
        lines.append(f"Your reasoning: {choice.thought}")
    if result_message:
        lines.append(f"Result: {result_message}")
    lines.append("Comment on it briefly, in character.")
    return "\n".join(lines)


class ActionDecider:
    """Picks game actions with an OpenAI-compatible LLM (e.g. Ollama) using tool calling."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float,
        persona: str,
    ):
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key or "none")
        self._model = model
        self._temperature = temperature
        self._persona = persona
        self._tool_choice_supported = True

    async def decide(
        self,
        game: str,
        context: List[str],
        actions: List[NeuroAction],
        state: Optional[str],
        query: str,
        required: bool,
        last_error: Optional[str] = None,
    ) -> Optional[ActionChoice]:
        """
        Ask the LLM to choose one of `actions`.

        Args:
            required: The game is waiting for an action (actions/force)

        Returns:
            The chosen action, or None if the LLM did not call any function.
        """
        request: Dict[str, Any] = {
            "model": self._model,
            "messages": build_decision_messages(
                self._persona, game, context, state, query, last_error
            ),
            "tools": [a.to_openai_tool() for a in actions],
            "temperature": self._temperature,
        }
        if required and self._tool_choice_supported:
            request["tool_choice"] = "required"

        try:
            response = await self._client.chat.completions.create(**request)
        except Exception as e:
            if "tool_choice" not in request:
                raise
            logger.debug(f"tool_choice not accepted ({e}), retrying without it")
            self._tool_choice_supported = False
            request.pop("tool_choice")
            response = await self._client.chat.completions.create(**request)

        message = response.choices[0].message
        if not message.tool_calls:
            return None
        call = message.tool_calls[0]
        thought = _THINK_TAG.sub("", message.content or "").strip()
        return ActionChoice(
            name=call.function.name,
            data=call.function.arguments or None,
            thought=thought[:300],
        )


class VTuberSpeaker:
    """
    Sends game turns to the VTuber through the proxy WebSocket, one at a time.

    While the VTuber is talking, new texts wait in a small buffer (oldest
    dropped first) and are merged into the next turn, so speech never lags far
    behind the game.
    """

    def __init__(
        self,
        proxy_url: str,
        max_pending: int = 3,
        response_timeout: float = 60.0,
        on_turn_finished: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        self._proxy_url = proxy_url
        self._pending: Deque[str] = deque(maxlen=max(1, max_pending))
        self._response_timeout = response_timeout
        self._on_turn_finished = on_turn_finished
        self._busy = False
        self._sent_at = 0.0

    def say(self, text: str) -> None:
        """Queue a text for the VTuber to react to."""
        if text.strip():
            self._pending.append(text.strip())

    async def run(self) -> None:
        """Keep a proxy connection open (reconnecting) and dispatch queued texts."""
        while True:
            try:
                async with websockets.connect(
                    self._proxy_url, ping_interval=20, ping_timeout=10
                ) as ws:
                    logger.info(f"Connected to VTuber proxy at {self._proxy_url}")
                    tasks = [
                        asyncio.create_task(self._receive_loop(ws)),
                        asyncio.create_task(self._dispatch_loop(ws)),
                    ]
                    try:
                        done, _ = await asyncio.wait(
                            tasks, return_when=asyncio.FIRST_COMPLETED
                        )
                        for task in done:
                            task.result()
                    finally:
                        for task in tasks:
                            task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"VTuber proxy connection lost ({e}); retrying in 3s")
            self._busy = False
            await asyncio.sleep(3)

    async def _receive_loop(self, ws) -> None:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                continue
            if (
                data.get("type") == "control"
                and data.get("text") == "conversation-chain-end"
                and self._busy
            ):
                self._busy = False
                if self._on_turn_finished:
                    await self._on_turn_finished()

    async def _dispatch_loop(self, ws) -> None:
        while True:
            await asyncio.sleep(0.2)
            now = time.monotonic()
            if self._busy:
                if now - self._sent_at < self._response_timeout:
                    continue
                logger.warning("No conversation end signal received in time")
                self._busy = False
            if not self._pending:
                continue
            text = "\n\n".join(self._pending)
            self._pending.clear()
            await ws.send(json.dumps({"type": "text-input", "text": text}))
            logger.info(f"Sent game turn to VTuber: {text}")
            self._busy = True
            self._sent_at = now


class GameSession:
    """State of one connected game."""

    def __init__(self, websocket, max_context: int):
        self.websocket = websocket
        self.game = "Unknown game"
        self.actions: Dict[str, NeuroAction] = {}
        self.context: Deque[str] = deque(maxlen=max(1, max_context))
        self.last_state: Optional[str] = None
        self.pending_results: Dict[str, asyncio.Future] = {}
        self.force_task: Optional[asyncio.Task] = None
        self.free_task: Optional[asyncio.Task] = None

    async def send(self, command: str, data: Optional[Dict[str, Any]] = None) -> None:
        message: Dict[str, Any] = {"command": command}
        if data is not None:
            message["data"] = data
        await self.websocket.send(json.dumps(message))

    def cancel_tasks(self) -> None:
        for task in (self.force_task, self.free_task):
            if task and not task.done():
                task.cancel()
        for future in self.pending_results.values():
            if not future.done():
                future.set_result(ActionResult(False, "Game disconnected."))
        self.pending_results.clear()


class NeuroGameBridge:
    """Websocket server speaking the Neuro Game API to games."""

    def __init__(
        self,
        decider: ActionDecider,
        speaker: Optional[VTuberSpeaker],
        max_retries: int = 3,
        max_context: int = 20,
        act_on_context: bool = False,
        comment_on_context: bool = True,
        comment_on_actions: bool = True,
    ):
        self._decider = decider
        self._speaker = speaker
        self._max_retries = max(0, max_retries)
        self._max_context = max_context
        self._act_on_context = act_on_context
        self._comment_on_context = comment_on_context
        self._comment_on_actions = comment_on_actions
        self._sessions: Set[GameSession] = set()

    async def serve(self, host: str, port: int) -> None:
        """Run the websocket server for games (forever)."""
        async with websockets.serve(self.handle_connection, host, port):
            logger.info(
                f"Neuro Game API listening on ws://{host}:{port} "
                f"(set NEURO_SDK_WS_URL=ws://{host}:{port} for the game)"
            )
            await asyncio.Future()

    async def notify_speech_finished(self) -> None:
        """Tell games the character finished talking (spec: speech_finished)."""
        for session in list(self._sessions):
            try:
                await session.send("speech_finished", {"isFinal": True})
            except Exception:
                pass

    async def handle_connection(self, websocket, *_) -> None:
        session = GameSession(websocket, self._max_context)
        self._sessions.add(session)
        logger.info("Game connected")
        try:
            async for raw in websocket:
                await self.handle_message(session, raw)
        except websockets.ConnectionClosed:
            pass
        finally:
            session.cancel_tasks()
            self._sessions.discard(session)
            logger.info(f"Game '{session.game}' disconnected")

    async def handle_message(self, session: GameSession, raw: Any) -> None:
        """Handle one message from the game. Malformed messages are ignored, per spec."""
        try:
            message = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(message, dict) or not isinstance(message.get("command"), str):
            return
        if isinstance(message.get("game"), str) and message["game"]:
            session.game = message["game"]
        data = message.get("data") if isinstance(message.get("data"), dict) else {}
        command = message["command"]

        if command == "startup":
            session.cancel_tasks()
            session.actions.clear()
            session.context.clear()
            session.last_state = None
            logger.info(f"Game startup: {session.game}")
        elif command == "context":
            self._on_context(session, data)
        elif command == "actions/register":
            for action in parse_actions(data.get("actions")):
                session.actions[action.name] = action
            logger.info(f"[{session.game}] actions: {sorted(session.actions)}")
        elif command == "actions/unregister":
            for name in data.get("action_names") or []:
                session.actions.pop(name, None)
        elif command == "actions/force":
            if session.force_task and not session.force_task.done():
                session.force_task.cancel()
            session.force_task = asyncio.create_task(self._run_force(session, data))
        elif command == "action/result":
            future = session.pending_results.pop(str(data.get("id")), None)
            if future and not future.done():
                future.set_result(
                    ActionResult(
                        bool(data.get("success")), str(data.get("message") or "")
                    )
                )

    def _on_context(self, session: GameSession, data: Dict[str, Any]) -> None:
        text = str(data.get("message") or "").strip()
        if not text:
            return
        session.context.append(text)
        if data.get("silent"):
            return
        if self._comment_on_context and self._speaker:
            self._speaker.say(f"[Game: {session.game}] {text}")
        forcing = session.force_task and not session.force_task.done()
        acting = session.free_task and not session.free_task.done()
        if self._act_on_context and session.actions and not forcing and not acting:
            session.free_task = asyncio.create_task(self._run_free_action(session))

    async def _run_force(self, session: GameSession, data: Dict[str, Any]) -> None:
        query = str(data.get("query") or "")
        state = data.get("state")
        state = str(state) if state is not None else session.last_state
        names = [n for n in data.get("action_names") or [] if isinstance(n, str)]
        last_error: Optional[str] = None

        try:
            for attempt in range(self._max_retries + 1):
                allowed = [session.actions[n] for n in names if n in session.actions]
                if not allowed:
                    logger.warning(
                        f"[{session.game}] force has no registered actions: {names}"
                    )
                    return
                choice = await self._decider.decide(
                    session.game,
                    list(session.context),
                    allowed,
                    state,
                    query,
                    True,
                    last_error,
                )
                error = self._check_choice(choice, session, names)
                if error:
                    logger.info(
                        f"[{session.game}] invalid choice (attempt {attempt + 1}): {error}"
                    )
                    last_error = error
                    continue
                result = await self._execute(
                    session, session.actions[choice.name], choice.data
                )
                if result.success:
                    if self._comment_on_actions and self._speaker:
                        self._speaker.say(
                            describe_choice(session.game, query, choice, result.message)
                        )
                    return
                last_error = result.message or "The action failed."
                logger.info(f"[{session.game}] action failed: {last_error}")
            logger.warning(
                f"[{session.game}] gave up after {self._max_retries + 1} attempts"
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[{session.game}] error while handling force: {e}")
        finally:
            if not data.get("ephemeral_context"):
                if data.get("state") is not None:
                    session.last_state = str(data["state"])
                if query:
                    session.context.append(f"(Asked) {query}")

    async def _run_free_action(self, session: GameSession) -> None:
        """Let the LLM optionally act on new context, without being forced."""
        try:
            actions = list(session.actions.values())
            choice = await self._decider.decide(
                session.game,
                list(session.context),
                actions,
                session.last_state,
                "Something happened. If an action makes sense right now, call it; "
                "otherwise do not call any function.",
                False,
            )
            if choice is None:
                return
            if self._check_choice(choice, session, [a.name for a in actions]):
                return
            result = await self._execute(
                session, session.actions[choice.name], choice.data
            )
            if result.success and self._comment_on_actions and self._speaker:
                self._speaker.say(
                    describe_choice(session.game, "", choice, result.message)
                )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[{session.game}] error while acting on context: {e}")

    @staticmethod
    def _check_choice(
        choice: Optional[ActionChoice], session: GameSession, allowed: List[str]
    ) -> Optional[str]:
        if choice is None:
            return "You must call exactly one of the provided functions."
        if choice.name not in allowed or choice.name not in session.actions:
            return f"'{choice.name}' is not an available action."
        return validate_action_data(session.actions[choice.name], choice.data)

    async def _execute(
        self, session: GameSession, action: NeuroAction, data: Optional[str]
    ) -> ActionResult:
        """Send an action to the game and wait for its action/result."""
        action_id = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        session.pending_results[action_id] = future
        payload: Dict[str, Any] = {"id": action_id, "name": action.name}
        if action.schema and data:
            payload["data"] = data
        logger.info(f"[{session.game}] action: {action.name} {payload.get('data', '')}")
        try:
            await session.send("action", payload)
            return await asyncio.wait_for(future, ACTION_RESULT_TIMEOUT)
        except asyncio.TimeoutError:
            return ActionResult(False, "The game did not answer in time.")
        finally:
            session.pending_results.pop(action_id, None)
