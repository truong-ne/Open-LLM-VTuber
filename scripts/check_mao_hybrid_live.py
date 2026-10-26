"""Check native Qwen tool calls and memory across fresh agents using synthetic data."""

import asyncio
import inspect
import json
from pathlib import Path
import sys
from unittest.mock import Mock
from urllib.parse import urlsplit
import uuid

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent  # noqa: E402
from src.open_llm_vtuber.agent.stateless_llm.openai_compatible_llm import AsyncLLM  # noqa: E402
from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource  # noqa: E402


async def main():
    document = yaml.safe_load((ROOT / "conf.yaml").read_text(encoding="utf-8"))
    config = document["character_config"]["agent_config"]
    basic = config["agent_settings"]["basic_memory_agent"]
    provider = config["llm_configs"][basic["llm_provider"]]
    if urlsplit(provider["base_url"]).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("This smoke check only sends synthetic data to a local model")
    settings = {**basic["hybrid"], "scope": "live-check-" + uuid.uuid4().hex}
    settings["computer"] = {"enabled": False}
    settings["exploration_enabled"] = False
    settings["persona_source"] = "config"  # isolated synthetic diagnostic, not the character
    model = AsyncLLM(
        model=provider["model"],
        base_url=provider["base_url"],
        temperature=0.1,
        extra_body={"reasoning_effort": "none"},
    )
    first = BasicMemoryAgent(
        model,
        "Synthetic tool diagnostic. Never invent identities or preferences.",
        Mock(),
        hybrid_config=settings,
    )
    second = None
    result = {"model": provider["model"], "turns": []}
    try:
        for index, text in enumerate(
            (
                "Hãy gọi công cụ remember để nhớ lâu rằng Bắp thích trà đào. Dùng nguyên văn đoạn 'Bắp thích trà đào' làm content, subject là Bắp; sau khi lưu hãy xác nhận ngắn.",
                "Hãy gọi công cụ recall để kiểm tra: Bắp thích đồ uống gì?",
            )
        ):
            if index:
                second = first.fork_session()
                result["fresh_agent_history_was_empty"] = not second._memory
                await first.close()
            agent = second if index else first
            output = [
                x
                async for x in inspect.unwrap(agent._chat_function_factory())(
                    BatchInput([TextData(TextSource.INPUT, text)])
                )
            ]
            result["turns"].append(
                {
                    "text": "".join(x for x in output if isinstance(x, str)),
                    "tool_errors": sum(
                        isinstance(x, dict) and x.get("status") == "error"
                        for x in output
                    ),
                    "tool_calls": sum(
                        isinstance(x, dict) and x.get("type") == "tool_call_status"
                        for x in output
                    ),
                }
            )
        rows = await asyncio.to_thread(second._hybrid.store.recall, "Bắp")
        result["stored_claims"] = len(rows)
        result["success"] = bool(
            rows
            and result["fresh_agent_history_was_empty"]
            and all(t["tool_calls"] and not t["tool_errors"] for t in result["turns"])
            and "trà đào" in result["turns"][1]["text"].casefold()
        )
        (ROOT / "logs/mao-hybrid-v2-live-check.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["success"]:
            raise RuntimeError(
                "Live tool/memory check did not meet its acceptance criteria"
            )
    finally:
        store = second._hybrid.store if second else first._hybrid.store
        with store.connect() as db:
            for table in ("memories", "state", "events", "approvals"):
                db.execute(
                    f"DELETE FROM mao_hybrid.{table} WHERE scope=%s",
                    (settings["scope"],),
                )
        if second:
            await second.close()
        else:
            await first.close()
        await model.client.close()


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), 120))
