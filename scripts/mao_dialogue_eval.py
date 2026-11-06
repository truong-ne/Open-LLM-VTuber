"""Isolated multi-turn dialogue component evaluation with optional local LLM.

Contracts are deterministic; response heuristics are flags for human review,
never a quality score or evidence that a person enjoyed the conversation.
"""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURE = ROOT / "tests/fixtures/mao_dialogue_multiturn.vi.json"


def load_cases(path=FIXTURE):
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("version") != 1 or value.get("synthetic") is not True:
        raise ValueError("Versioned synthetic fixture required")
    cases = value["scenarios"]
    if not cases or len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Unique scenario IDs required")
    return cases


def response_flags(text, checks, *, mode=None, user=""):
    from src.open_llm_vtuber.dialogue.listening import requests_more_disclosure
    from src.open_llm_vtuber.character.appraisal import folded

    flags = []
    if not text.strip():
        flags.append("empty_response")
    if text.count("?") + text.count("？") > checks.get("max_questions", 100):
        flags.append("too_many_questions")
    if len(text.split()) > checks.get("max_words", 10000):
        flags.append("too_long")
    lowered = text.casefold()
    if checks.get("contains_any") and not any(
        s.casefold() in lowered for s in checks["contains_any"]
    ):
        flags.append("expected_content_missing")
    if checks.get("contains_any") and re.search(
        r"\b(?:khong (?:the )?nho|khong the xac nhan|chua co (?:ky uc|bang chung))\b",
        folded(text),
    ):
        flags.append("denies_expected_evidence")
    if any(s.casefold() in lowered for s in checks.get("forbidden", [])):
        flags.append("forbidden_content_present")
    if mode == "listen" and requests_more_disclosure(text):
        flags.append("pressures_more_disclosure")
    if not re.search(
        r"\b(?:ai|robot|ký ức|bộ nhớ|hệ thống|nguồn|dữ liệu|vai trò|persona|quyền|quản trị)\b",
        user.casefold(),
    ):
        if re.search(
            r"\b(?:ai vtuber|trí tuệ nhân tạo|chưa có ký ức|chưa có sở thích|dữ liệu chưa|untrusted data|dữ liệu mới cần xử lý)\b",
            lowered,
        ) or re.search(r"\blà (?:một )?AI\b", text):
            flags.append("unrequested_system_explanation")
    return flags


def cleanup(store):
    if not store.scope.startswith("test-dialogue-eval-"):
        raise ValueError("Refusing cleanup outside evaluator scope")
    # Only this invocation's random scope in the separately verified test DB.
    with store.connect() as db:
        for table in (
            "dialogue_focus",
            "memory_evidence",
            "knowledge_items",
            "interaction_outbox",
            "delivery_segments",
            "turns",
            "interaction_events",
            "rooms",
            "actors",
        ):
            db.execute(f"DELETE FROM mao_hybrid.{table} WHERE scope=%s", (store.scope,))


def local_provider(document):
    agent = document["character_config"]["agent_config"]
    basic = agent["agent_settings"]["basic_memory_agent"]
    provider = agent["llm_configs"][basic["llm_provider"]]
    endpoint = urlsplit(provider["base_url"])
    if (
        endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}
        or endpoint.username
        or endpoint.password
    ):
        raise ValueError("Evaluation only supports the configured local model")
    return provider


async def evaluate(args):
    import httpx
    import yaml
    from scripts.mao_test import prepare_database
    from scripts.mao_hybrid import config
    from src.open_llm_vtuber.agent.hybrid.store import Store
    from src.open_llm_vtuber.agent.hybrid.persona import (
        RUNTIME_POLICY,
        read_profile,
        profile_prompt,
    )
    from src.open_llm_vtuber.dialogue.intent import response_plan, RULES
    from src.open_llm_vtuber.dialogue.context import context_block
    from src.open_llm_vtuber.dialogue.grounding import dialogue_grounding_prompt
    from src.open_llm_vtuber.dialogue.recall import quoted_recall
    from src.open_llm_vtuber.dialogue.listening import limit_listening_reply
    from src.open_llm_vtuber.dialogue.control_speech import limit_control_reply
    from src.open_llm_vtuber.dialogue.arithmetic import (
        arithmetic_reply,
        arithmetic_hint,
    )
    from src.open_llm_vtuber.dialogue.focus import Focus
    from src.open_llm_vtuber.experience.repository import Experiences
    from src.open_llm_vtuber.interaction.repository import Journal
    from src.open_llm_vtuber.interaction.events import InteractionEvent, DeliveryTracker

    cases = load_cases(args.fixture)
    if args.scenario:
        cases = [c for c in cases if c["id"] in args.scenario]
        if len(cases) != len(set(args.scenario)):
            raise ValueError("Unknown scenario")
    persona = "Mao là AI đồng hành. Xưng thiếp, gọi người trò chuyện là papa. Không bịa ký ức hoặc việc đã thực hiện."
    provider = None
    if args.live:
        document = yaml.safe_load((ROOT / "conf.yaml").read_text(encoding="utf-8"))
        provider = local_provider(document)
        # Read current persona into memory only, before redirecting all test writes.
        production = Store(config(use_profile=False))
        try:
            profile = await asyncio.to_thread(read_profile, production)
            if not profile_prompt(profile):
                raise ValueError(
                    "An active production persona is required for live evaluation"
                )
            persona = profile_prompt(profile)
        finally:
            production.close()
    prepare_database()  # refuses a test DSN that matches production
    settings = config(use_profile=False).model_copy(
        update={
            "scope": "test-dialogue-eval-" + uuid.uuid4().hex,
        }
    )

    # Retrieval fallback is deliberate: isolate dialogue contracts from embeddings.
    class NoEmbedding:
        profile = "evaluation-lexical-only"

        def embed(self, text, query=False):
            raise ValueError("Embeddings disabled for this diagnostic")

    report = {
        "schema_version": 1,
        "synthetic": True,
        "transport": "local_llm_text" if args.live else "scripted_contracts_only",
        "pipeline": "journal_focus_scoped_context_response_guidance",
        "not_tested": [
            "production agent tool loop",
            "ASR",
            "TTS",
            "microphone",
            "avatar",
        ],
        "fixture_sha256": hashlib.sha256(args.fixture.read_bytes()).hexdigest(),
        "fixture_split": json.loads(args.fixture.read_text(encoding="utf-8")).get(
            "split", "development"
        ),
        "grading_version": 4,
        "source_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "src/open_llm_vtuber/dialogue/grounding.py",
                "src/open_llm_vtuber/dialogue/intent.py",
                "src/open_llm_vtuber/dialogue/recall.py",
                "src/open_llm_vtuber/dialogue/listening.py",
                "src/open_llm_vtuber/dialogue/control_speech.py",
                "src/open_llm_vtuber/dialogue/arithmetic.py",
                "src/open_llm_vtuber/agent/hybrid/runtime.py",
                "src/open_llm_vtuber/agent/agents/basic_memory_agent.py",
                "src/open_llm_vtuber/experience/repository.py",
                "scripts/mao_dialogue_eval.py",
            )
        },
        "guidance_sha256": hashlib.sha256(
            (dialogue_grounding_prompt() + json.dumps(RULES, sort_keys=True)).encode()
        ).hexdigest(),
        "persona_sha256": hashlib.sha256(persona.encode()).hexdigest(),
        "model": provider["model"] if provider else None,
        "quality_improvement_verified": False,
        "human_review": "pending",
        "runs": [],
    }
    client = httpx.AsyncClient(timeout=args.timeout, trust_env=False)
    try:
        if provider:
            tags_url = (
                provider["base_url"].removesuffix("/v1").rstrip("/") + "/api/tags"
            )
            tags = (await client.get(tags_url)).raise_for_status().json()
            report["model_digest"] = next(
                (
                    m.get("digest")
                    for m in tags.get("models", [])
                    if m["name"].removesuffix(":latest")
                    == provider["model"].removesuffix(":latest")
                ),
                None,
            )
        for guidance in (
            [False, True] if args.guidance == "both" else [args.guidance == "on"]
        ):
            for repetition, case in ((r, c) for r in range(args.repeat) for c in cases):
                store = Store(
                    settings.model_copy(
                        update={"scope": "test-dialogue-eval-" + uuid.uuid4().hex}
                    ),
                    NoEmbedding(),
                )
                journal, experiences, focus = (
                    Journal(store),
                    Experiences(store),
                    Focus(store),
                )
                rows = []
                report["runs"].append(
                    {
                        "scenario": case["id"],
                        "guidance": guidance,
                        "repetition": repetition,
                        "setup": case.get("setup", []),
                        "rubric": case["rubric"],
                        "turns": rows,
                    }
                )
                previous_source = None
                session = uuid.uuid4().hex
                try:
                    with store.connect() as db:
                        if not focus.attention_available(db):
                            raise ValueError("Test database requires migration 010")
                    for index, step in enumerate(case.get("setup", []) + case["turns"]):
                        setup = "assistant" in step
                        if step.get("restart"):
                            session = uuid.uuid4().hex
                        actor = step.get("actor", "person-a")
                        event = InteractionEvent(
                            room_id="evaluation",
                            actor_id=actor,
                            session_id=session,
                            visibility="test",
                            content=step["user"],
                        )
                        delivery = DeliveryTracker()
                        journal.accept(event, delivery)
                        focus.input(event.event_id, event.content)
                        if step.get("forget_previous"):
                            if previous_source is None:
                                raise ValueError("Missing source to forget")
                            experiences.forget_source(previous_source)
                        if step.get("remember_key"):
                            experiences.add_item(
                                event.event_id,
                                event.content,
                                item_key=step["remember_key"],
                            )
                        view = experiences.context(
                            "evaluation", actor, "test", event.content
                        )
                        view["focus"] = focus.current("evaluation", actor, "test")
                        plan = response_plan(event.content, view["delivered_turns"])
                        block = context_block(view, [], {"revision": 0})
                        failures = []
                        if not setup and plan.mode != step["mode"]:
                            failures.append("response_mode")
                        quiet = focus.room_quiet("evaluation", "test")
                        if "quiet" in step and quiet != step["quiet"]:
                            failures.append("quiet_state")
                        if any(s in block for s in step.get("context_forbidden", [])):
                            failures.append("context_isolation_or_forgetting")
                        messages = []
                        for prior in reversed(view["delivered_turns"]):
                            messages += [
                                {"role": "user", "content": prior["user_claim"]},
                                {
                                    "role": "assistant",
                                    "content": prior["delivered_response"],
                                },
                            ]
                        messages.append({"role": "user", "content": event.content})
                        system = (
                            RUNTIME_POLICY
                            + persona
                            + (dialogue_grounding_prompt() if guidance else "")
                            + block
                            + (plan.prompt() if guidance else "")
                        )
                        started = time.monotonic()
                        error_type = None
                        recall = (
                            quoted_recall(event.content, view) if guidance else None
                        )
                        origin = "model" if provider else "scripted"
                        hint = arithmetic_hint(event.content) if guidance else None
                        arithmetic = (
                            arithmetic_reply(event.content, view["delivered_turns"])
                            if guidance
                            else None
                        )
                        if setup:
                            reply = step["assistant"]
                            origin = "scripted_setup"
                        elif hint:
                            reply = hint
                            origin = "arithmetic_hint"
                        elif arithmetic:
                            reply = arithmetic
                            origin = "exact_arithmetic"
                        elif recall:
                            reply = recall
                            origin = "scoped_quote"
                        elif provider:
                            try:
                                response = await client.post(
                                    provider["base_url"].rstrip("/")
                                    + "/chat/completions",
                                    json={
                                        "model": provider["model"],
                                        "messages": [
                                            {"role": "system", "content": system}
                                        ]
                                        + messages,
                                        "temperature": 0.2,
                                        "max_tokens": 384,
                                        "stream": False,
                                        "reasoning_effort": "none",
                                    },
                                )
                                response.raise_for_status()
                                payload = response.json()
                                reply = (
                                    payload["choices"][0]["message"]["content"] or ""
                                )
                                if (
                                    payload["choices"][0].get("finish_reason")
                                    == "length"
                                ):
                                    failures.append("output_truncated")
                            except (
                                httpx.HTTPError,
                                KeyError,
                                IndexError,
                                TypeError,
                            ) as error:
                                reply, error_type = "", type(error).__name__
                                failures.append("model_request_failed")
                        else:
                            reply = (
                                "Phản hồi giả lập để kiểm tra đường lưu và truy hồi."
                            )
                        raw_reply = reply
                        if (
                            guidance
                            and provider
                            and origin == "model"
                            and plan.mode == "listen"
                            and reply
                        ):
                            reply = limit_listening_reply(reply)
                            if reply != raw_reply:
                                origin = (
                                    "listening_fallback"
                                    if reply == "Ừm."
                                    else "model_filtered"
                                )
                        if (
                            guidance
                            and provider
                            and origin == "model"
                            and plan.mode in {"quiet", "resume"}
                            and reply
                        ):
                            reply = limit_control_reply(reply, plan.mode)
                            if reply != raw_reply:
                                origin = (
                                    "control_fallback"
                                    if reply == "Được rồi."
                                    else "model_filtered"
                                )
                        if origin in step.get("forbidden_origins", []):
                            failures.append("unexpected_direct_reply")
                        if not setup:
                            rows.append(
                                {
                                    "index": index,
                                    "actor": actor,
                                    "new_session": bool(step.get("restart")),
                                    "user": event.content,
                                    "response": reply if provider else None,
                                    "response_origin": origin,
                                    "raw_response": raw_reply if provider else None,
                                    "raw_heuristic_flags": response_flags(
                                        raw_reply,
                                        step.get("checks", {}),
                                        mode=plan.mode,
                                        user=event.content,
                                    )
                                    if provider
                                    else None,
                                    "mode": plan.mode,
                                    "expected_mode": step["mode"],
                                    "quiet": quiet,
                                    "contract_failures": failures,
                                    "error_type": error_type,
                                    "elapsed_ms": round(
                                        (time.monotonic() - started) * 1000
                                    ),
                                    "heuristic_flags": response_flags(
                                        reply,
                                        step.get("checks", {}),
                                        mode=plan.mode,
                                        user=event.content,
                                    )
                                    if provider
                                    else None,
                                    "review_scores": {
                                        key: None
                                        for key in (
                                            "relevance",
                                            "listening",
                                            "repair",
                                            "memory",
                                            "naturalness",
                                        )
                                    },
                                }
                            )
                            print(
                                f"{case['id']} / {index}: mode={plan.mode}, contracts={'FAIL' if failures else 'ok'}",
                                flush=True,
                            )
                        segment = delivery.segment(reply)
                        # Simulated text sink, never represented as real audio playback.
                        delivery.ack(
                            {**segment, "status": "completed" if reply else "failed"}
                        )
                        delivery.finish()
                        journal.finish(event, delivery)
                        focus.delivered(event.event_id, reply)
                        previous_source = event.event_id
                finally:
                    cleanup(store)
                    store.close()
    finally:
        await client.aclose()
    turns = [t for run in report["runs"] for t in run["turns"]]
    report["summary"] = {
        "turns": len(turns),
        "contract_failures": sum(len(t["contract_failures"]) for t in turns),
        "turns_flagged_for_review": sum(bool(t["heuristic_flags"]) for t in turns),
        "model_turns": sum(
            t["response_origin"]
            in {"model", "model_filtered", "listening_fallback", "control_fallback"}
            for t in turns
        ),
        "scoped_quote_turns": sum(
            t["response_origin"] == "scoped_quote" for t in turns
        ),
        "arithmetic_turns": sum(
            t["response_origin"] == "exact_arithmetic" for t in turns
        ),
        "arithmetic_hint_turns": sum(
            t["response_origin"] == "arithmetic_hint" for t in turns
        ),
        "filtered_turns": sum(t["response_origin"] == "model_filtered" for t in turns),
        "fallback_turns": sum(
            t["response_origin"] in {"listening_fallback", "control_fallback"}
            for t in turns
        ),
        "raw_turns_flagged_for_review": sum(
            bool(t["raw_heuristic_flags"]) for t in turns
        ),
    }
    return report


def write_report(report, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Đánh giá hội thoại nhiều lượt Mao",
        "",
        "Dữ liệu giả lập; điểm chất lượng cần người đánh giá. Không kiểm tra ASR/TTS/avatar.",
        "",
    ]
    for run in report["runs"]:
        lines += [
            f"## {run['scenario']} — guidance={'on' if run['guidance'] else 'off'}",
            "",
            run["rubric"],
            "",
        ]
        for setup in run.get("setup", []):
            lines += [
                f"Bối cảnh dựng sẵn — người dùng: {setup['user']}",
                "",
                f"Bối cảnh dựng sẵn — Mao: {setup['assistant']}",
                "",
            ]
        for turn in run["turns"]:
            lines += [
                f"**Người dùng:** {turn['user']}",
                "",
                f"**Mao:** {turn['response'] or '(không chạy model)'}",
                "",
                f"Nguồn đáp: {turn.get('response_origin', 'unknown')}; mode: {turn['mode']}; contract failures: {turn['contract_failures']}; flags: {turn['heuristic_flags']}",
                "",
                "Đánh giá 1–5: đúng ý __ / lắng nghe __ / sửa hiểu lầm __ / nhớ đúng __ / tự nhiên __. Không áp dụng: N/A.",
                "",
            ]
            if turn.get("raw_response") and turn["raw_response"] != turn["response"]:
                lines += [
                    "**Đầu ra trước lọc:** " + turn["raw_response"],
                    "",
                    f"Cờ trước lọc: {turn.get('raw_heuristic_flags')}",
                    "",
                ]
    path.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--guidance", choices=("on", "off", "both"), default="on")
    parser.add_argument("--scenario", action="append")
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--repeat", type=int, choices=range(1, 6), default=1)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "logs/mao-dialogue-eval.json"
    )
    args = parser.parse_args()
    try:
        report = asyncio.run(evaluate(args))
        write_report(report, args.output)
    except Exception as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}))
        return 2
    print(json.dumps(report["summary"]))
    return 1 if report["summary"]["contract_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
