from typing import Any, Dict, List, Optional, Union
import asyncio
import json
from loguru import logger
from fastapi import WebSocket
import numpy as np

from ..agent.output_types import AudioOutput, SentenceOutput

from .conversation_utils import (
    create_batch_input,
    process_agent_output,
    process_user_input,
    finalize_conversation_turn,
    cleanup_conversation,
    EMOJI_LIST,
)
from .types import (
    BroadcastFunc,
    GroupConversationState,
    BroadcastContext,
    WebSocketSend,
)
from ..service_context import ServiceContext
from ..chat_history_manager import store_message
from .tts_manager import TTSTaskManager


async def process_group_conversation(
    client_contexts,
    client_connections,
    broadcast_func,
    group_members,
    initiator_client_uid,
    user_input,
    images=None,
    session_emoji="😊",
    metadata=None,
):
    from ..interaction.service import enabled
    from ..interaction.coordinator import coordinator

    context = client_contexts[initiator_client_uid]
    if enabled(context):
        from ..interaction.ingress import unseal, seal, verify_actor, issue_actor

        if not unseal((metadata or {}).get("_host_ingress")):
            token = getattr(context, "mao_actor_token", None)
            if not verify_actor(token):
                token = context.mao_actor_token = issue_actor()
            import hashlib

            room = (
                "group:"
                + hashlib.sha256("|".join(sorted(group_members)).encode()).hexdigest()
            )
            metadata = {
                **(metadata or {}),
                "_host_ingress": seal(
                    verify_actor(token), initiator_client_uid, public=True, room=room
                ),
            }
    args = (
        client_contexts,
        client_connections,
        broadcast_func,
        group_members,
        initiator_client_uid,
        user_input,
        images,
        session_emoji,
        metadata,
    )
    if enabled(context):
        async with coordinator(context.agent_engine._hybrid.store.scope).floor(
            "group_" + initiator_client_uid
        ):
            admitted = (metadata or {}).get("_admitted_turn")
            if admitted and admitted.persist:
                await asyncio.to_thread(admitted.journal.start, admitted.delivery)
            try:
                return await _process_group_conversation(*args)
            finally:
                if admitted:
                    await admitted.finish()
    return await _process_group_conversation(*args)


async def _process_group_conversation(
    client_contexts: Dict[str, ServiceContext],
    client_connections: Dict[str, WebSocket],
    broadcast_func: BroadcastFunc,
    group_members: List[str],
    initiator_client_uid: str,
    user_input: Union[str, np.ndarray],
    images: Optional[List[Dict[str, Any]]] = None,
    session_emoji: str = np.random.choice(EMOJI_LIST),
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Process group conversation

    Args:
        client_contexts: Dictionary of client contexts
        client_connections: Dictionary of client WebSocket connections
        broadcast_func: Function to broadcast messages to group
        group_members: List of group member UIDs
        initiator_client_uid: UID of conversation initiator
        user_input: Text or audio input from user
        images: Optional list of image data
        session_emoji: Emoji identifier for the conversation
        metadata: Optional metadata for special processing flags
    """
    # Create TTSTaskManager for each member
    tts_managers = {uid: TTSTaskManager() for uid in group_members}

    try:
        logger.info(f"Group Conversation Chain {session_emoji} started!")

        # Initialize state with group_id
        state = GroupConversationState(
            group_id=f"group_{initiator_client_uid}",  # Use same format as chat_group
            session_emoji=session_emoji,
            group_queue=list(group_members),
            memory_index={
                uid: 0 for uid in group_members
            },  # Initialize memory index for each member
        )

        # Initialize group conversation context for each AI
        init_group_conversation_contexts(client_contexts)

        # Get human name from initiator context
        initiator_context = client_contexts.get(initiator_client_uid)
        human_name = (
            initiator_context.character_config.human_name
            if initiator_context
            else "Human"
        )

        # Process initial input
        input_text = await process_group_input(
            user_input=user_input,
            initiator_context=initiator_context,
            initiator_ws_send=client_connections[initiator_client_uid].send_text,
            broadcast_func=broadcast_func,
            group_members=group_members,
            initiator_client_uid=initiator_client_uid,
        )
        state.mao_user_input = input_text

        # Check if we should skip storing this input to history
        skip_history = metadata and metadata.get("skip_history", False)

        from ..interaction.service import enabled

        durable = enabled(initiator_context)
        if not skip_history and not durable:
            for member_uid in group_members:
                member_context = client_contexts[member_uid]
                store_message(
                    conf_uid=member_context.character_config.conf_uid,
                    history_uid=member_context.history_uid,
                    role="human",
                    content=input_text,
                    name=human_name,
                )
        else:
            logger.debug("Skipping storing proactive speak input to group history")

        state.conversation_history = [f"{human_name}: {input_text}"]

        is_first_responder = True
        remaining = len(group_members) if durable else None
        # Main conversation loop
        while state.group_queue:
            if remaining is not None:
                if remaining <= 0:
                    break
                remaining -= 1
            try:
                current_member_uid = state.group_queue.pop(0)

                # Only pass metadata to the first responder
                current_metadata = None
                if durable:
                    current_metadata = metadata
                if is_first_responder:
                    current_metadata = metadata
                    is_first_responder = False

                await handle_group_member_turn(
                    current_member_uid=current_member_uid,
                    state=state,
                    client_contexts=client_contexts,
                    client_connections=client_connections,
                    broadcast_func=broadcast_func,
                    group_members=group_members,
                    images=images,
                    tts_manager=tts_managers[current_member_uid],
                    metadata=current_metadata,
                )
            except Exception as e:
                logger.error(f"Error in group member turn: {e}")
                await handle_member_error(
                    broadcast_func, group_members, f"Error in conversation: {str(e)}"
                )

    except asyncio.CancelledError:
        logger.info(
            f"🤡👍 Group Conversation {session_emoji} cancelled because interrupted."
        )
        raise
    except Exception as e:
        logger.error(f"Error in group conversation chain: {e}")
        await handle_member_error(
            broadcast_func, group_members, f"Fatal error in conversation: {str(e)}"
        )
        raise
    finally:
        # Cleanup all TTS managers
        for tts_manager in tts_managers.values():
            cleanup_conversation(tts_manager, session_emoji)
        # Clean up
        GroupConversationState.remove_state(state.group_id)


def init_group_conversation_state(
    group_members: List[str], session_emoji: str
) -> GroupConversationState:
    """Initialize group conversation state"""
    return GroupConversationState(
        conversation_history=[],
        memory_index={uid: 0 for uid in group_members},
        group_queue=list(group_members),
        session_emoji=session_emoji,
    )


def init_group_conversation_contexts(
    client_contexts: Dict[str, ServiceContext],
) -> None:
    """Initialize group conversation context for each AI participant"""
    ai_names = [ctx.character_config.character_name for ctx in client_contexts.values()]

    for context in client_contexts.values():
        agent = context.agent_engine
        if hasattr(agent, "start_group_conversation"):
            agent.start_group_conversation(
                human_name="Human",
                ai_participants=[
                    name
                    for name in ai_names
                    if name != context.character_config.character_name
                ],
            )
            logger.debug(
                f"Initialized group conversation context for "
                f"{context.character_config.character_name}"
            )


async def process_group_input(
    user_input: Union[str, np.ndarray],
    initiator_context: ServiceContext,
    initiator_ws_send: WebSocketSend,
    broadcast_func: BroadcastFunc,
    group_members: List[str],
    initiator_client_uid: str,
) -> str:
    """Process and broadcast user input to group"""
    input_text = await process_user_input(
        user_input, initiator_context.asr_engine, initiator_ws_send
    )
    await broadcast_transcription(
        broadcast_func, group_members, input_text, initiator_client_uid
    )
    return input_text


async def broadcast_transcription(
    broadcast_func: BroadcastFunc,
    group_members: List[str],
    text: str,
    exclude_uid: str,
) -> None:
    """Broadcast transcription to group members"""
    await broadcast_func(
        group_members,
        {
            "type": "user-input-transcription",
            "text": text,
        },
        exclude_uid,
    )


async def handle_group_member_turn(**kwargs):
    from ..interaction.service import enabled, TurnSession
    from ..interaction.events import current_delivery

    context = kwargs["client_contexts"][kwargs["current_member_uid"]]
    if not enabled(context):
        return await _handle_group_member_turn(**kwargs)
    metadata = {
        **(kwargs.get("metadata") or {}),
        "_group_member": kwargs["current_member_uid"],
    }
    turn = TurnSession(context, kwargs["current_member_uid"], metadata)
    token = current_delivery.set(turn.delivery)
    try:
        if not await turn.begin(kwargs["state"].mao_user_input):
            return
        metadata = {
            **(kwargs.get("metadata") or {}),
            "_interaction": await turn.input(kwargs["state"].mao_user_input),
        }
        return await _handle_group_member_turn(
            **{**kwargs, "metadata": metadata}, mao_turn=turn
        )
    except asyncio.CancelledError:
        await asyncio.shield(turn.finish("interrupted"))
        raise
    except Exception:
        await turn.finish("failed")
        raise
    finally:
        try:
            if turn.delivery.state == "running":
                await turn.finish()
        finally:
            current_delivery.reset(token)


async def _handle_group_member_turn(
    current_member_uid: str,
    state: GroupConversationState,
    client_contexts: Dict[str, ServiceContext],
    client_connections: Dict[str, WebSocket],
    broadcast_func: BroadcastFunc,
    group_members: List[str],
    images: Optional[List[Dict[str, Any]]],
    tts_manager: TTSTaskManager,
    metadata: Optional[Dict[str, Any]] = None,
    mao_turn=None,
) -> None:
    """Handle a single group member's conversation turn"""
    # Update current speaker before processing
    state.current_speaker_uid = current_member_uid

    await broadcast_thinking_state(broadcast_func, group_members)

    context = client_contexts[current_member_uid]
    current_ws_send = client_connections[current_member_uid].send_text
    if mao_turn:
        original_send = current_ws_send

        async def current_ws_send(message):
            await mao_turn.send(message, original_send)

    new_messages = state.conversation_history[state.memory_index[current_member_uid] :]
    new_context = "\n".join(new_messages) if new_messages else ""

    batch_input = create_batch_input(
        input_text=new_context,
        images=images,
        from_name="Human",
        metadata=metadata,
    )

    logger.info(
        f"AI {context.character_config.character_name} "
        f"(client {current_member_uid}) receiving {len(new_context)} context characters"
    )

    full_response = await process_member_response(
        context=context,
        batch_input=batch_input,
        current_ws_send=current_ws_send,
        tts_manager=tts_manager,
        broadcast_func=broadcast_func,
        group_members=group_members,
    )

    if tts_manager.task_list:
        await asyncio.gather(*tts_manager.task_list)

        broadcast_ctx = BroadcastContext(
            broadcast_func=broadcast_func,
            group_members=group_members,
            current_client_uid=current_member_uid,
        )

        await finalize_conversation_turn(
            tts_manager=tts_manager,
            websocket_send=current_ws_send,
            client_uid=current_member_uid,
            broadcast_ctx=broadcast_ctx,
        )

    if full_response:
        ai_message = f"{context.character_config.character_name}: {full_response}"
        state.conversation_history.append(ai_message)
        logger.info("Group response generated ({} characters)", len(full_response))

        for member_uid in group_members:
            if mao_turn:
                continue
            member_context = client_contexts[member_uid]
            store_message(
                conf_uid=member_context.character_config.conf_uid,
                history_uid=member_context.history_uid,
                role="ai",
                content=full_response,
                name=context.character_config.character_name,
                avatar=context.character_config.avatar,
            )
        else:
            logger.debug("Skipping storing AI response to history (proactive speak)")

    state.memory_index[current_member_uid] = len(state.conversation_history)
    state.group_queue.append(current_member_uid)

    # Clear speaker after turn completes
    state.current_speaker_uid = None


async def broadcast_thinking_state(
    broadcast_func: BroadcastFunc, group_members: List[str]
) -> None:
    """Broadcast thinking state to group"""
    await broadcast_func(
        group_members,
        {"type": "control", "text": "conversation-chain-start"},
    )
    await broadcast_func(
        group_members,
        {"type": "full-text", "text": "Thinking..."},
    )


async def handle_member_error(
    broadcast_func: BroadcastFunc,
    group_members: List[str],
    error_message: str,
) -> None:
    """Handle and broadcast member error"""
    await broadcast_func(
        group_members,
        {
            "type": "error",
            "message": error_message,
        },
    )


async def process_member_response(
    context: ServiceContext,
    batch_input: Any,
    current_ws_send: WebSocketSend,
    tts_manager: TTSTaskManager,
    broadcast_func: Optional[BroadcastFunc] = None,
    group_members: Optional[List[str]] = None,
) -> str:
    """Process group member's response, handling text/audio and tool status events."""
    full_response = ""

    try:
        # agent.chat now yields Union[SentenceOutput, Dict[str, Any]]
        turn = getattr(context, "mao_turn_session", None)
        if turn and turn.delivery.state == "running":
            from ..dialogue.engine import DialogueEngine

            agent_output_stream = DialogueEngine(
                context.agent_engine, turn.policy
            ).chat(batch_input)
        else:
            agent_output_stream = context.agent_engine.chat(batch_input)

        async for output_item in agent_output_stream:
            if (
                isinstance(output_item, dict)
                and output_item.get("type") == "tool_call_status"
            ):
                if broadcast_func and group_members:
                    logger.debug(f"Broadcasting tool status update: {output_item}")
                    output_item["name"] = context.character_config.character_name
                    await broadcast_func(group_members, output_item)
                else:
                    logger.warning(
                        "Cannot broadcast tool status: broadcast_func or group_members missing."
                    )
            elif isinstance(output_item, (SentenceOutput, AudioOutput)):
                # Handle SentenceOutput or AudioOutput: Send to current user, broadcast audio later if needed
                response_part = await process_agent_output(
                    output=output_item,
                    character_config=context.character_config,
                    live2d_model=context.live2d_model,
                    tts_engine=context.tts_engine,
                    websocket_send=current_ws_send,  # Send TTS/display text directly to speaker's client
                    tts_manager=tts_manager,
                    translate_engine=context.translate_engine,
                )
                full_response += response_part  # Accumulate text response
            else:
                logger.warning(
                    f"Received unexpected item type from agent chat stream: {type(output_item)}"
                )

    except Exception as e:
        logger.exception(f"Error processing group member response stream: {e}")
        await current_ws_send(
            json.dumps(
                {"type": "error", "message": f"Error processing response: {str(e)}"}
            )
        )

    return full_response
