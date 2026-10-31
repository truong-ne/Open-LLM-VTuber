"""Process-local overlays. Never rewrite the operator's YAML configuration."""

from copy import deepcopy
import os

PROFILES = ("local_dev", "test", "local_companion", "live")
TEST_SCOPE = "mao-synthetic-test"


def apply_profile(document, profile=None):
    profile = profile or os.environ.get("MAO_RUNTIME_PROFILE")
    result = deepcopy(document)
    if not profile:
        return result  # Existing entry points retain their configured behavior.
    if profile not in PROFILES:
        raise ValueError("Unknown Mao runtime profile")
    if profile == "live":
        return result
    result.setdefault("system_config", {})["host"] = "127.0.0.1"
    live = result.setdefault("live_config", {})
    live["active_platform"] = "local"
    live.setdefault("bilibili_live", {})["room_ids"] = []
    live.setdefault("tiktok_live", {})["unique_id"] = ""
    live.setdefault("youtube_live", {}).update(channel="", video_url="")
    character = result["character_config"]
    agent = character["agent_config"]
    basic = agent["agent_settings"].get("basic_memory_agent")
    if agent["conversation_agent_choice"] != "basic_memory_agent" or not basic:
        raise ValueError("Mao local/test profiles require basic_memory_agent")
    hybrid = basic.setdefault("hybrid", {})
    hybrid.update(exploration_enabled=False, learning_enabled=False)
    hybrid.setdefault("computer", {})["enabled"] = False
    hybrid.setdefault("autonomy", {})["enabled"] = False
    if profile in {"local_dev", "test"}:
        basic.update(use_mcpp=False, mcp_enabled_servers=[])
    if profile == "test":
        result["system_config"]["port"] = 12394
        character.update(
            conf_uid="mao_synthetic_test", persona_prompt="Synthetic diagnostic AI."
        )
        hybrid.update(
            database_url_env="MAO_TEST_DATABASE_URL",
            database_env_file="private/mao-test.env",
            scope=TEST_SCOPE,
            persona_source="config",
        )
    return result


def effective_summary(config):
    """Allowlist fields; never serialize prompts, credentials or entire configs."""
    character = config.character_config
    agent = character.agent_config
    summary = {
        "profile": os.environ.get("MAO_RUNTIME_PROFILE", "configured"),
        "host": config.system_config.host,
        "port": config.system_config.port,
        "platform": config.live_config.active_platform,
        "agent": agent.conversation_agent_choice,
        "asr": character.asr_config.asr_model,
        "tts": character.tts_config.tts_model,
    }
    basic = agent.agent_settings.basic_memory_agent
    if agent.conversation_agent_choice != "basic_memory_agent" or basic is None:
        return {**summary, "llm_provider": None, "model": None, "flags": {}}
    hybrid = basic.hybrid
    provider = getattr(agent.llm_configs, basic.llm_provider)
    return {
        **summary,
        "llm_provider": basic.llm_provider,
        "model": getattr(provider, "model", None),
        "flags": {
            "hybrid": hybrid.enabled,
            "emotion": hybrid.emotion_enabled,
            "interaction": hybrid.interaction_enabled,
            "coordinator": hybrid.coordinator_enabled,
            "shadow": hybrid.coordinator_shadow,
            "auto_policy_promotion": hybrid.auto_policy_promotion,
            "persona_source": hybrid.persona_source,
            "mcp": basic.use_mcpp,
            "exploration": hybrid.exploration_enabled,
            "learning": hybrid.learning_enabled,
            "computer": hybrid.computer.enabled,
            "autonomy": hybrid.autonomy.enabled,
        },
    }
