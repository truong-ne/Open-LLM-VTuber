from typing import Union, List, Dict, Any, Optional
import asyncio
import json
import time
from loguru import logger
import numpy as np

from .conversation_utils import (
    create_batch_input,
    process_agent_output,
    send_conversation_start_signals,
    process_user_input,
    finalize_conversation_turn,
    cleanup_conversation,
    EMOJI_LIST,
)
from .types import WebSocketSend
from .tts_manager import TTSTaskManager
from ..chat_history_manager import store_message
from ..service_context import ServiceContext

# Import necessary types from agent outputs
from ..agent.output_types import SentenceOutput, AudioOutput


async def process_single_conversation(
    context: ServiceContext,
    websocket_send: WebSocketSend,
    client_uid: str,
    user_input: Union[str, np.ndarray],
    images: Optional[List[Dict[str, Any]]] = None,
    session_emoji: str = np.random.choice(EMOJI_LIST),
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Process a single-user conversation turn

    Args:
        context: Service context containing all configurations and engines
        websocket_send: WebSocket send function
        client_uid: Client unique identifier
        user_input: Text or audio input from user
        images: Optional list of image data
        session_emoji: Emoji identifier for the conversation
        metadata: Optional metadata for special processing flags

    Returns:
        str: Complete response text
    """
    # Create TTSTaskManager for this conversation
    tts_manager = TTSTaskManager()
    full_response = ""  # Initialize full_response here
    started = time.monotonic()
    metrics = {"audio_chunks": 0, "errors": 0, "cancelled": 0}
    original_send = websocket_send

    async def measured_send(message):
        payload = json.loads(message)
        if payload.get("type") == "audio" and payload.get("audio"):
            metrics["audio_chunks"] += 1
            metrics.setdefault("first_audio_ms", (time.monotonic() - started) * 1000)
        if payload.get("type") == "error":
            metrics["errors"] += 1
        await original_send(message)

    hybrid = getattr(context.agent_engine, "_hybrid", None)
    learning_enabled = bool(hybrid) and hybrid.config.learning_enabled is True
    if learning_enabled and not (metadata and (metadata.get("game_speech") or metadata.get("narration_speech"))):
        websocket_send = measured_send
    input_text = ""

    try:
        # Send initial signals
        await send_conversation_start_signals(websocket_send)
        logger.info(f"New Conversation Chain {session_emoji} started!")

        if metadata and (metadata.get("game_speech") or metadata.get("narration_speech")):
            from ..agent.output_types import DisplayText
            from ..live.game_speech import (
                game_speech_chunks,
                game_speech_prosody,
                prepared_game_engine,
            )

            script = metadata.get("game_speech") or metadata["narration_speech"]
            is_game = bool(metadata.get("game_speech"))
            from ..live.narration_speech import (
                narration_chunks, narration_text, NarrationPlanner,
            )
            planner = NarrationPlanner()
            phrases = game_speech_chunks(script) if is_game else narration_chunks(script)
            for phrase in phrases:
                speech = game_speech_prosody(phrase) if is_game else planner.plan(phrase)
                spoken = phrase if is_game else narration_text(phrase)
                if not spoken:
                    continue
                await tts_manager.speak(
                    tts_text=spoken,
                    display_text=DisplayText(
                        text=spoken,
                        name=context.character_config.character_name,
                        avatar=context.character_config.avatar,
                    ),
                    actions=None,
                    live2d_model=context.live2d_model,
                    tts_engine=prepared_game_engine(context.tts_engine) if is_game else context.tts_engine,
                    websocket_send=websocket_send,
                    speech=speech,
                )
                # Send each phrase as soon as it is synthesized. Generate the
                # next while the client plays this one, with one TTS job at a
                # time rather than competing GPU jobs for the entire script.
                await tts_manager.wait_for_completion()
            await finalize_conversation_turn(tts_manager, websocket_send, client_uid)
            return script

        # Process user input
        input_text = await process_user_input(
            user_input, context.asr_engine, websocket_send
        )
        if not input_text.strip():
            # Silence is not a conversational turn for the language model.
            await finalize_conversation_turn(
                tts_manager=tts_manager,
                websocket_send=websocket_send,
                client_uid=client_uid,
            )
            return ""

        # Create batch input
        batch_input = create_batch_input(
            input_text=input_text,
            images=images,
            from_name=context.character_config.human_name,
            metadata=metadata,
        )

        # Store user message (check if we should skip storing to history)
        skip_history = metadata and metadata.get("skip_history", False)
        if context.history_uid and not skip_history:
            store_message(
                conf_uid=context.character_config.conf_uid,
                history_uid=context.history_uid,
                role="human",
                content=input_text,
                name=context.character_config.human_name,
            )

        if skip_history:
            logger.debug("Skipping storing user input to history (proactive speak)")

        logger.info(f"User input: {input_text}")
        if images:
            logger.info(f"With {len(images)} images")

        try:
            # agent.chat yields Union[SentenceOutput, Dict[str, Any]]
            agent_output_stream = context.agent_engine.chat(batch_input)

            async for output_item in agent_output_stream:
                if isinstance(output_item, dict) and output_item.get("type") in (
                    "tool_call_status",
                    "error",
                ):
                    # Handle tool status event: send WebSocket message
                    output_item["name"] = context.character_config.character_name
                    logger.debug(f"Sending tool status update: {output_item}")

                    await websocket_send(json.dumps(output_item))

                elif isinstance(output_item, (SentenceOutput, AudioOutput)):
                    # Handle SentenceOutput or AudioOutput
                    response_part = await process_agent_output(
                        output=output_item,
                        character_config=context.character_config,
                        live2d_model=context.live2d_model,
                        tts_engine=context.tts_engine,
                        websocket_send=websocket_send,  # Pass websocket_send for audio/tts messages
                        tts_manager=tts_manager,
                        translate_engine=context.translate_engine,
                    )
                    # Ensure response_part is treated as a string before concatenation
                    response_part_str = (
                        str(response_part) if response_part is not None else ""
                    )
                    full_response += response_part_str  # Accumulate text response
                else:
                    logger.warning(
                        f"Received unexpected item type from agent chat stream: {type(output_item)}"
                    )
                    logger.debug(f"Unexpected item content: {output_item}")

        except Exception as e:
            logger.exception(
                f"Error processing agent response stream: {e}"
            )  # Log with stack trace
            await websocket_send(
                json.dumps(
                    {
                        "type": "error",
                        "message": f"Error processing agent response: {str(e)}",
                    }
                )
            )
            # full_response will contain partial response before error
        # --- End processing agent response ---

        await finalize_conversation_turn(
            tts_manager=tts_manager,
            websocket_send=websocket_send,
            client_uid=client_uid,
        )

        if context.history_uid and full_response:  # Check full_response before storing
            store_message(
                conf_uid=context.character_config.conf_uid,
                history_uid=context.history_uid,
                role="ai",
                content=full_response,
                name=context.character_config.character_name,
                avatar=context.character_config.avatar,
            )
            logger.info(f"AI response: {full_response}")

        return full_response  # Return accumulated full_response

    except asyncio.CancelledError:
        metrics["cancelled"] = 1
        logger.info(f"🤡👍 Conversation {session_emoji} cancelled because interrupted.")
        raise
    except Exception as e:
        logger.error(f"Error in conversation chain: {e}")
        await websocket_send(
            json.dumps({"type": "error", "message": f"Conversation error: {str(e)}"})
        )
        raise
    finally:
        cleanup_conversation(tts_manager, session_emoji)
        if learning_enabled and input_text.strip():
            from ..agent.hybrid.learning import DailyLearning
            from ..agent.proactive_reply import HOST_PREFIX

            metrics["duration_ms"] = (time.monotonic() - started) * 1000
            kind = "proactive" if input_text.startswith(HOST_PREFIX) else "conversation"
            if metadata and metadata.get("rehearsal"):
                kind = "rehearsal"
            try:
                identifier = await asyncio.to_thread(
                    DailyLearning(hybrid.store).record,
                    full_response,
                    metrics,
                    kind,
                    hybrid.learning_profile["version"],
                )
                logger.info("Learning turn recorded: {}", identifier)
            except Exception as error:
                logger.warning("Learning metrics unavailable: {}", type(error).__name__)
