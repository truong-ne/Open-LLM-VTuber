from loguru import logger

from ..agent.output_types import AudioOutput, SentenceOutput


class DialogueEngine:
    """Small wrapper: consume only the pinned turn policy, close cancelled streams."""

    def __init__(self, agent, policy):
        self.agent, self.policy = agent, policy

    async def chat(self, data):
        maximum = (
            3 if self.policy.get("settings", {}).get("verbosity") == "brief" else 32
        )
        # Check after sentence/tag/TTS filtering: tokens or expression tags alone
        # do not prove that a turn has speech. Never replay a native tool loop.
        recovery = getattr(self.agent, "recover_silent_reply", None)
        for attempt in range(2):
            stream = (
                recovery(data)
                if attempt and callable(recovery)
                else self.agent.chat(data)
            )
            spoken = 0
            saw_event = False
            saw_error = False
            try:
                async for item in stream:
                    if isinstance(item, SentenceOutput):
                        if not any(char.isalnum() for char in item.tts_text):
                            continue
                        if spoken >= maximum:
                            return
                        spoken += 1
                    elif isinstance(item, AudioOutput):
                        spoken += 1
                    else:
                        saw_event = True
                        saw_error |= (
                            isinstance(item, dict) and item.get("type") == "error"
                        )
                    yield item
            finally:
                close = getattr(stream, "aclose", None)
                if close:
                    await close()
            if spoken or saw_error:
                return
            if (
                attempt == 0
                and not saw_event
                and (callable(recovery) or not getattr(self.agent, "_use_mcpp", True))
            ):
                from ..interaction.events import current_delivery

                trace = current_delivery.get()
                if trace:
                    trace.metrics["empty_reply_retries"] = 1
                logger.warning(
                    "No speakable agent output; requesting one speech-only recovery"
                )
                continue
            yield {
                "type": "error",
                "code": "empty-agent-reply",
                "message": "Mao chưa tạo được lời thoại ở lượt này. Bạn thử lại nhé.",
            }
            return
