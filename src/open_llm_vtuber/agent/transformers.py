from typing import AsyncIterator, Tuple, Callable, List, Union, Dict, Any
from functools import wraps
from .output_types import Actions, SentenceOutput, DisplayText
from ..utils.tts_preprocessor import tts_filter as filter_text
from ..live2d_model import Live2dModel
from ..config_manager import TTSPreprocessorConfig
from ..utils.sentence_divider import SentenceDivider
from ..utils.sentence_divider import SentenceWithTags, TagState
from loguru import logger
from ..tts.prosody import TurnSpeechPlanner, hide_native_cues
from .body_context import extract_body_tag, read_body_state
from .motor_intent import extract_pose_tag, PoseStreamGuard
from uuid import uuid4


def sentence_divider(
    faster_first_response: bool = True,
    segment_method: str = "pysbd",
    valid_tags: List[str] = None,
):
    """
    Decorator that transforms token stream into sentences with tags

    Args:
        faster_first_response: bool - Whether to enable faster first response
        segment_method: str - Method for sentence segmentation
        valid_tags: List[str] - List of valid tags to process
    """

    def decorator(
        func: Callable[
            ..., AsyncIterator[Union[str, Dict[str, Any]]]
        ],  # Expects str or dict
    ) -> Callable[
        ..., AsyncIterator[Union[SentenceWithTags, Dict[str, Any]]]
    ]:  # Yields SentenceWithTags or dict
        @wraps(func)
        async def wrapper(
            *args, **kwargs
        ) -> AsyncIterator[Union[SentenceWithTags, Dict[str, Any]]]:
            divider = SentenceDivider(
                faster_first_response=faster_first_response,
                segment_method=segment_method,
                valid_tags=valid_tags or [],
            )
            stream_from_func = func(*args, **kwargs)
            pose_guard = PoseStreamGuard()

            async def guarded_stream():
                async for event in stream_from_func:
                    if isinstance(event, str):
                        safe = pose_guard.feed(event)
                        if safe:
                            yield safe
                    else:
                        yield event
                tail = pose_guard.feed("", final=True)
                if tail:
                    yield tail

            # Process the mixed stream using the updated SentenceDivider
            async for item in divider.process_stream(guarded_stream()):
                if isinstance(item, SentenceWithTags):
                    item.text = pose_guard.restore(item.text)
                    logger.debug(f"sentence_divider yielding sentence: {item}")
                elif isinstance(item, dict):
                    logger.debug(f"sentence_divider yielding dict: {item}")
                yield item  # Yield either SentenceWithTags or dict
            # Flushing is handled within divider.process_stream

        return wrapper

    return decorator


def actions_extractor(live2d_model: Live2dModel):
    """
    Decorator that extracts actions from sentences, passing through dicts.
    """

    def decorator(
        func: Callable[
            ..., AsyncIterator[Union[SentenceWithTags, Dict[str, Any]]]
        ],  # Input type hint
    ) -> Callable[
        ..., AsyncIterator[Union[Tuple[SentenceWithTags, Actions], Dict[str, Any]]]
    ]:  # Output type hint
        @wraps(func)
        async def wrapper(
            *args, **kwargs
        ) -> AsyncIterator[
            Union[Tuple[SentenceWithTags, Actions], Dict[str, Any]]
        ]:  # Yield type hint
            stream = func(*args, **kwargs)
            body_used = False
            pending_body = None
            pending_pose = None
            async for item in stream:
                if isinstance(item, SentenceWithTags):
                    sentence = item
                    actions = Actions()
                    # Only extract emotions for non-tag text
                    if not any(
                        tag.state in [TagState.START, TagState.END]
                        for tag in sentence.tags
                    ):
                        sentence.text, pose = extract_pose_tag(sentence.text)
                        if pose:
                            pending_pose = pose
                        sentence.text, body_command = extract_body_tag(sentence.text)
                        if body_command and not body_used and not pending_body:
                            pending_body = body_command
                        if pending_body and sentence.text.strip() and not body_used:
                            state = read_body_state()
                            if (
                                state
                                and state.get("mode") == "window"
                                and state.get("bodyPhase") == "idle"
                                and not state.get("bodyStopped")
                            ):
                                actions.body = {
                                    "id": uuid4().hex,
                                    "command": pending_body,
                                }
                            body_used = True
                            pending_body = None
                        if body_command and not sentence.text.strip():
                            continue
                        expressions = live2d_model.extract_emotion(sentence.text)
                        # A gesture such as [shy] also carries a vocal intention.
                        # Keep it for the planner before removing it from speech
                        # and subtitles; it must never become a spoken label.
                        sentence.speech_text = sentence.text
                        if expressions:
                            actions.expressions = expressions
                        motions = live2d_model.context_motions_for_sentence(
                            sentence.text
                        )
                        if motions:
                            actions.motions = motions
                            sentence.text = live2d_model.remove_context_motion_tags(
                                sentence.text
                            )
                        if pending_pose and sentence.text.strip():
                            actions.pose = pending_pose
                            pending_pose = None
                        if not sentence.text.strip():
                            continue
                    yield sentence, actions  # Yield the tuple
                elif isinstance(item, dict):
                    # Pass through dictionaries
                    yield item
                else:
                    logger.warning(
                        f"actions_extractor received unexpected type: {type(item)}"
                    )

        return wrapper

    return decorator


def display_processor():
    """
    Decorator that processes text for display, passing through dicts.
    """

    def decorator(
        func: Callable[
            ..., AsyncIterator[Union[Tuple[SentenceWithTags, Actions], Dict[str, Any]]]
        ],  # Input type hint
    ) -> Callable[
        ...,
        AsyncIterator[
            Union[Tuple[SentenceWithTags, DisplayText, Actions], Dict[str, Any]]
        ],
    ]:  # Output type hint
        @wraps(func)
        async def wrapper(
            *args, **kwargs
        ) -> AsyncIterator[
            Union[Tuple[SentenceWithTags, DisplayText, Actions], Dict[str, Any]]
        ]:  # Yield type hint
            stream = func(*args, **kwargs)

            async for item in stream:
                if (
                    isinstance(item, tuple)
                    and len(item) == 2
                    and isinstance(item[0], SentenceWithTags)
                ):
                    sentence, actions = item
                    text = sentence.text
                    # Handle think tag states
                    for tag in sentence.tags:
                        if tag.name == "think":
                            if tag.state == TagState.START:
                                text = "("
                            elif tag.state == TagState.END:
                                text = ")"

                    display = DisplayText(text=text)  # Simplified DisplayText creation
                    yield sentence, display, actions  # Yield the tuple
                elif isinstance(item, dict):
                    # Pass through dictionaries
                    yield item
                else:
                    logger.warning(
                        f"display_processor received unexpected type: {type(item)}"
                    )

        return wrapper

    return decorator


def tts_filter(
    tts_preprocessor_config: TTSPreprocessorConfig = None,
):
    """
    Decorator that filters text for TTS, passing through dicts.
    Skips TTS for think tag content.
    """

    def decorator(
        func: Callable[
            ...,
            AsyncIterator[
                Union[Tuple[SentenceWithTags, DisplayText, Actions], Dict[str, Any]]
            ],
        ],  # Input type hint
    ) -> Callable[
        ..., AsyncIterator[Union[SentenceOutput, Dict[str, Any]]]
    ]:  # Output type hint
        @wraps(func)
        async def wrapper(
            *args, **kwargs
        ) -> AsyncIterator[Union[SentenceOutput, Dict[str, Any]]]:  # Yield type hint
            stream = func(*args, **kwargs)
            config = tts_preprocessor_config or TTSPreprocessorConfig()
            speech_planner = TurnSpeechPlanner()

            async for item in stream:
                if (
                    isinstance(item, tuple)
                    and len(item) == 3
                    and isinstance(item[1], DisplayText)
                ):
                    sentence, display, actions = item
                    speech = None
                    if any(tag.name == "think" for tag in sentence.tags):
                        tts = ""
                    else:
                        speech = speech_planner.plan(
                            sentence.speech_text or display.text
                        )
                        display.text = hide_native_cues(display.text)
                        tts = filter_text(
                            text=display.text,
                            remove_special_char=config.remove_special_char,
                            ignore_brackets=config.ignore_brackets,
                            ignore_parentheses=config.ignore_parentheses,
                            ignore_asterisks=config.ignore_asterisks,
                            ignore_angle_brackets=config.ignore_angle_brackets,
                            vietnamese_math=getattr(config, "vietnamese_math", False),
                        )

                    logger.debug(f"[{display.name}] display: {display.text}")
                    logger.debug(f"[{display.name}] tts: {tts}")

                    yield SentenceOutput(
                        display_text=display,
                        tts_text=tts,
                        actions=actions,
                        speech=speech,
                    )
                elif isinstance(item, dict):
                    # Pass through dictionaries
                    yield item
                else:
                    logger.warning(f"tts_filter received unexpected type: {type(item)}")

        return wrapper

    return decorator
