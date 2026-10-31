import asyncio
import json
from collections import deque
from typing import Dict, Optional, Callable

import numpy as np
from fastapi import WebSocket
from loguru import logger

from ..chat_group import ChatGroupManager
from ..chat_history_manager import store_message
from ..service_context import ServiceContext
from .group_conversation import process_group_conversation
from .single_conversation import process_single_conversation
from .conversation_utils import EMOJI_LIST
from .types import GroupConversationState
from prompts import prompt_loader


async def handle_conversation_trigger(
    msg_type: str,
    data: dict,
    client_uid: str,
    context: ServiceContext,
    websocket: WebSocket,
    client_contexts: Dict[str, ServiceContext],
    client_connections: Dict[str, WebSocket],
    chat_group_manager: ChatGroupManager,
    received_data_buffers: Dict[str, np.ndarray],
    current_conversation_tasks: Dict[str, Optional[asyncio.Task]],
    broadcast_to_group: Callable,
) -> None:
    """Handle triggers that start a conversation"""
    metadata = None

    if msg_type == "ai-speak-signal":
        if (
            data.get("idle_time")
            and "pet_action_prompt" in context.system_config.tool_prompts
        ):
            logger.debug(
                "Ignoring idle speech trigger while context pet mode is enabled"
            )
            return
        try:
            # Get proactive speak prompt from config
            prompt_name = "proactive_speak_prompt"
            prompt_file = context.system_config.tool_prompts.get(prompt_name)
            if prompt_file:
                user_input = prompt_loader.load_util(prompt_file)
            else:
                logger.warning("Proactive speak prompt not configured, using default")
                user_input = "Please say something."
        except Exception as e:
            logger.error(f"Error loading proactive speak prompt: {e}")
            user_input = "Please say something."

        # Add metadata to indicate this is a proactive speak request
        # that should be skipped in both memory and history
        metadata = {
            "proactive_speak": True,
            "skip_memory": True,  # Skip storing in AI's internal memory
            "skip_history": True,  # Skip storing in local conversation history
        }

        await websocket.send_text(
            json.dumps(
                {
                    "type": "full-text",
                    "text": "AI wants to speak something...",
                }
            )
        )
    elif msg_type == "text-input":
        from ..interaction.ingress import verify_host_proposal
        from ..interaction.service import enabled

        host_authorized = not enabled(context) or verify_host_proposal(data)
        if host_authorized and data.get("source") == "mao-idle-host":
            metadata = {
                "proactive_speak": True,
                "skip_memory": True,
                "skip_history": True,
                "_host_proposal": True,
            }
        if (
            host_authorized
            and data.get("source") == "mao-idle-host"
            and isinstance(data.get("narration_speech"), str)
        ):
            metadata = {
                "narration_speech": data["narration_speech"][:1400],
                "skip_history": True,
                "skip_memory": True,
                "_host_proposal": True,
            }
        if data.get("source") == "mao-rehearsal":
            metadata = {"rehearsal": True, "skip_history": True, "skip_memory": True}
        if (
            host_authorized
            and data.get("source") == "vua-tieng-viet"
            and isinstance(data.get("game_speech"), str)
        ):
            metadata = {
                "game_speech": data["game_speech"][:500],
                "_host_proposal": True,
                "skip_history": True,
                "skip_memory": True,
            }
        user_input = data.get("text", "")
    else:  # mic-audio-end
        user_input = received_data_buffers[client_uid]
        received_data_buffers[client_uid] = np.array([])

    images = data.get("images")
    if data.get("source") == "mao-rehearsal":
        metadata = {"rehearsal": True, "skip_history": True, "skip_memory": True}
    from ..interaction.ingress import unseal

    if unseal(data.get("_host_ingress")):
        metadata = {**(metadata or {}), "_host_ingress": data["_host_ingress"]}
    session_emoji = np.random.choice(EMOJI_LIST)

    group = chat_group_manager.get_client_group(client_uid)
    from ..interaction.service import enabled

    if enabled(context) and context.agent_engine._hybrid.config.coordinator_shadow:
        from ..interaction.coordinator import coordinator

        coordinator(context.agent_engine._hybrid.store.scope).shadow_inputs += 1
    if enabled(context):
        from ..interaction.coordinator import coordinator, Proposal
        from ..interaction.service import TurnSession
        from ..interaction.ingress import issue_actor, verify_actor, seal

        if not (metadata or {}).get("_host_ingress"):
            token = getattr(context, "mao_actor_token", None)
            if not verify_actor(token):
                token = context.mao_actor_token = issue_actor()
            source_key = data.get("event_id")
            if not isinstance(source_key, str) or not 0 < len(source_key) <= 150:
                source_key = None
            metadata = {
                **(metadata or {}),
                "_host_ingress": seal(
                    verify_actor(token),
                    client_uid,
                    source_key,
                    bool((metadata or {}).get("_host_proposal")),
                    provider="host"
                    if (metadata or {}).get("_host_proposal")
                    else "local",
                ),
            }
        if group and len(group.members) > 1:
            identity = unseal(metadata["_host_ingress"])
            metadata["_host_ingress"] = seal(
                identity["actor"],
                identity["session"],
                identity.get("source_key"),
                True,
                room="group:" + group.group_id,
                provider=identity.get("provider", "local"),
            )
        metadata = {
            **(metadata or {}),
            "_modality": "voice" if msg_type == "mic-audio-end" else "text",
        }
        admitted = TurnSession(context, client_uid, metadata)
        if not await admitted.admit(
            user_input if isinstance(user_input, str) else None
        ):
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "input-status",
                        "status": "duplicate",
                        "event_id": data.get("event_id"),
                    }
                )
            )
            return
        metadata = {**(metadata or {}), "_admitted_turn": admitted}

    if (
        enabled(context)
        and context.agent_engine._hybrid.config.coordinator_enabled
        and not context.agent_engine._hybrid.config.coordinator_shadow
    ):
        key = group.group_id if group and len(group.members) > 1 else client_uid

        async def notify(status):
            if status in {
                "rejected_busy",
                "expired",
                "superseded",
                "failed",
                "interrupted",
            }:
                await admitted.finish(
                    "rejected"
                    if status in {"rejected_busy", "expired", "superseded"}
                    else "interrupted"
                    if status == "interrupted"
                    else "failed"
                )
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "input-status",
                        "status": status,
                        "event_id": data.get("event_id"),
                    }
                )
            )

        async def run():
            if group and len(group.members) > 1:
                await process_group_conversation(
                    client_contexts,
                    client_connections,
                    broadcast_to_group,
                    list(group.members),
                    client_uid,
                    user_input,
                    images,
                    session_emoji,
                    metadata,
                )
            else:
                await process_single_conversation(
                    context,
                    websocket.send_text,
                    client_uid,
                    user_input,
                    images,
                    session_emoji,
                    metadata,
                )

        source = data.get("source", "")
        kind = (
            "proactive"
            if msg_type == "ai-speak-signal" or source == "mao-idle-host"
            else "activity"
            if metadata and metadata.get("game_speech")
            else "direct"
        )
        await coordinator(context.agent_engine._hybrid.store.scope).submit(
            Proposal(
                kind,
                run,
                notify,
                owner=key,
                deadline=__import__("time").monotonic() + 300,
            )
        )
        return
    if group and len(group.members) > 1:
        # Use group_id as task key for group conversations
        task_key = group.group_id
        if (
            task_key not in current_conversation_tasks
            or current_conversation_tasks[task_key].done()
        ):
            logger.info(f"Starting new group conversation for {task_key}")

            current_conversation_tasks[task_key] = asyncio.create_task(
                process_group_conversation(
                    client_contexts=client_contexts,
                    client_connections=client_connections,
                    broadcast_func=broadcast_to_group,
                    group_members=group.members,
                    initiator_client_uid=client_uid,
                    user_input=user_input,
                    images=images,
                    session_emoji=session_emoji,
                    metadata=metadata,
                )
            )
        else:
            receipt = (metadata or {}).get("_admitted_turn")
            if receipt:
                await receipt.finish("rejected")
            await websocket.send_text(
                json.dumps({"type": "input-status", "status": "rejected_busy"})
            )
    else:
        # Microphone turns also reach this handler directly, outside the proxy's
        # text queue. One worker owns agent memory and playback for this client.
        queue = getattr(context, "_individual_turn_queue", None)
        if queue is None:
            queue = context._individual_turn_queue = deque()
        if len(queue) >= 20:
            receipt = (metadata or {}).get("_admitted_turn")
            if receipt:
                await receipt.finish("rejected")
            await websocket.send_text(
                json.dumps({"type": "input-status", "status": "rejected_busy"})
            )
            return
        queue.append(
            dict(
                context=context,
                websocket_send=websocket.send_text,
                client_uid=client_uid,
                user_input=user_input,
                images=images,
                session_emoji=session_emoji,
                metadata=metadata,
            )
        )
        active = current_conversation_tasks.get(client_uid)
        if active and not active.done():
            return

        async def drain():
            try:
                while queue:
                    turn = queue.popleft()
                    try:
                        await process_single_conversation(**turn)
                    except Exception as error:
                        logger.error("Conversation turn failed: {}", error)
                        await websocket.send_text(
                            json.dumps(
                                {"type": "control", "text": "conversation-chain-end"}
                            )
                        )
            finally:
                for pending in queue:
                    receipt = (pending.get("metadata") or {}).get("_admitted_turn")
                    if receipt:
                        await asyncio.shield(receipt.finish("interrupted"))
                queue.clear()

        current_conversation_tasks[client_uid] = asyncio.create_task(drain())


async def handle_individual_interrupt(
    client_uid: str,
    current_conversation_tasks: Dict[str, Optional[asyncio.Task]],
    context: ServiceContext,
    heard_response: str,
):
    from ..interaction.service import enabled

    if enabled(context) and context.agent_engine._hybrid.config.coordinator_enabled:
        from ..interaction.coordinator import coordinator

        delivery = getattr(context, "mao_delivery", None)
        heard_response = (
            " ".join(
                s["content"]
                for s in delivery.segments.values()
                if s["status"] == "completed"
            )
            if delivery
            else ""
        )
        if not context.agent_engine._hybrid.config.coordinator_shadow:
            await coordinator(context.agent_engine._hybrid.store.scope).interrupt(
                client_uid
            )
            context.agent_engine.handle_interrupt(heard_response)
            return
    if client_uid in current_conversation_tasks:
        task = current_conversation_tasks[client_uid]
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info("🛑 Conversation task was successfully interrupted")

        try:
            context.agent_engine.handle_interrupt(heard_response)
        except Exception as e:
            logger.error(f"Error handling interrupt: {e}")

        if context.history_uid:
            store_message(
                conf_uid=context.character_config.conf_uid,
                history_uid=context.history_uid,
                role="ai",
                content=heard_response,
                name=context.character_config.character_name,
                avatar=context.character_config.avatar,
            )
            store_message(
                conf_uid=context.character_config.conf_uid,
                history_uid=context.history_uid,
                role="system",
                content="[Interrupted by user]",
            )


async def handle_group_interrupt(
    group_id: str,
    heard_response: str,
    current_conversation_tasks: Dict[str, Optional[asyncio.Task]],
    chat_group_manager: ChatGroupManager,
    client_contexts: Dict[str, ServiceContext],
    broadcast_to_group: Callable,
) -> None:
    """Handles interruption for a group conversation"""
    from ..interaction.service import enabled
    from ..interaction.coordinator import coordinator

    group = chat_group_manager.get_group_by_id(group_id)
    contexts = (
        [client_contexts[uid] for uid in group.members if uid in client_contexts]
        if group
        else []
    )
    host = next((ctx for ctx in contexts if enabled(ctx)), None)
    if (
        host
        and host.agent_engine._hybrid.config.coordinator_enabled
        and not host.agent_engine._hybrid.config.coordinator_shadow
    ):
        state = GroupConversationState.get_state(group_id)
        speaker = client_contexts.get(state.current_speaker_uid) if state else host
        delivery = getattr(speaker, "mao_delivery", None)
        heard = (
            " ".join(
                s["content"]
                for s in delivery.segments.values()
                if s["status"] == "completed"
            )
            if delivery
            else ""
        )
        await coordinator(host.agent_engine._hybrid.store.scope).interrupt(group_id)
        for member in contexts:
            member.agent_engine.handle_interrupt(heard)
        await broadcast_to_group(
            list(group.members),
            {"type": "interrupt-signal", "text": "conversation-interrupted"},
        )
        return
    task = current_conversation_tasks.get(group_id)
    if not task or task.done():
        return

    # Get state and speaker info before cancellation
    state = GroupConversationState.get_state(group_id)
    current_speaker_uid = state.current_speaker_uid if state else None

    # Get context from current speaker
    context = None
    group = chat_group_manager.get_group_by_id(group_id)
    if current_speaker_uid:
        context = client_contexts.get(current_speaker_uid)
        logger.info(f"Found current speaker context for {current_speaker_uid}")
    if not context and group and group.members:
        logger.warning(f"No context found for group {group_id}, using first member")
        context = client_contexts.get(next(iter(group.members)))

    # Now cancel the task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info(f"🛑 Group conversation {group_id} cancelled successfully.")

    current_conversation_tasks.pop(group_id, None)
    GroupConversationState.remove_state(group_id)  # Clean up state after we've used it

    # Store messages with speaker info
    if context and group:
        for member_uid in group.members:
            if member_uid in client_contexts:
                try:
                    member_ctx = client_contexts[member_uid]
                    member_ctx.agent_engine.handle_interrupt(heard_response)
                    if enabled(member_ctx):
                        continue
                    store_message(
                        conf_uid=member_ctx.character_config.conf_uid,
                        history_uid=member_ctx.history_uid,
                        role="ai",
                        content=heard_response,
                        name=context.character_config.character_name,
                        avatar=context.character_config.avatar,
                    )
                    store_message(
                        conf_uid=member_ctx.character_config.conf_uid,
                        history_uid=member_ctx.history_uid,
                        role="system",
                        content="[Interrupted by user]",
                    )
                except Exception as e:
                    logger.error(f"Error handling interrupt for {member_uid}: {e}")

    await broadcast_to_group(
        list(group.members),
        {
            "type": "interrupt-signal",
            "text": "conversation-interrupted",
        },
    )
