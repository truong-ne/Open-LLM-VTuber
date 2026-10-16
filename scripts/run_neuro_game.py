import os
import sys
import asyncio
from loguru import logger

# Add project root to path to enable imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from src.open_llm_vtuber.live.neuro_game import (
    ActionDecider,
    NeuroGameBridge,
    VTuberSpeaker,
)
from src.open_llm_vtuber.config_manager.utils import read_yaml, validate_config


async def main():
    """
    Run the Neuro Game API bridge.
    Games made for Neuro-sama connect here, the character picks their actions
    and comments on the game through the VTuber proxy.
    """
    logger.info("Starting Neuro Game API bridge")

    config_path = os.path.join(project_root, "conf.yaml")
    config = validate_config(read_yaml(config_path))
    game_config = config.live_config.neuro_game
    character = config.character_config

    # Use the same LLM endpoint as the character (must be OpenAI-compatible)
    agent_config = character.agent_config
    provider = agent_config.agent_settings.basic_memory_agent.llm_provider
    llm_config = getattr(agent_config.llm_configs, provider, None)
    base_url = getattr(llm_config, "base_url", None)
    if not base_url:
        logger.error(
            f"LLM provider '{provider}' has no base_url. Use an OpenAI-compatible "
            "provider such as 'ollama_llm', 'lmstudio_llm' or 'openai_compatible_llm'."
        )
        return

    decider = ActionDecider(
        base_url=base_url,
        api_key=getattr(llm_config, "llm_api_key", None) or "none",
        model=game_config.model or llm_config.model,
        temperature=game_config.temperature,
        persona=character.persona_prompt,
    )

    bridge: NeuroGameBridge
    speaker = VTuberSpeaker(
        proxy_url=f"ws://localhost:{config.system_config.port}/proxy-ws",
        max_pending=game_config.max_pending_comments,
        on_turn_finished=lambda: bridge.notify_speech_finished(),
    )
    bridge = NeuroGameBridge(
        decider=decider,
        speaker=speaker,
        max_retries=game_config.max_retries,
        max_context=game_config.max_context,
        act_on_context=game_config.act_on_context,
        comment_on_context=game_config.comment_on_context,
        comment_on_actions=game_config.comment_on_actions,
    )

    if not config.system_config.enable_proxy:
        logger.warning(
            "system_config.enable_proxy is false: the character cannot talk about the game. "
            "Set it to true in conf.yaml."
        )

    await asyncio.gather(
        bridge.serve(game_config.host, game_config.port),
        speaker.run(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down Neuro Game API bridge")

# Usage: uv run python scripts/run_neuro_game.py
