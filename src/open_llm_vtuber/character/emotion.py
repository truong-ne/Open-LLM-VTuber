"""Versioned functional affect with inertia, decay, regulation and action policy.

Persist only bounded numbers/enums and opaque IDs; no transcript, bond score,
biological need, persona mutation or permissions live in this state.
"""

import math
import re
import time

from .appraisal import Appraisal, appraise_text, background_appraisal

MODES = {
    "calm": (0.0, 0.2),
    "curious": (0.2, 0.45),
    "warm": (0.4, 0.35),
    "thoughtful": (0.05, 0.25),
    "attentive": (0.0, 0.15),
}
EVENTS = {
    "audience_input",
    "study_started",
    "source_explained",
    "lesson_saved",
    "task_result",
}
BASE = {
    "pleasure": 0.0,
    "arousal": 0.2,
    "agency": 0.0,
    "certainty": 0.5,
    "novelty": 0.0,
}
CHANNELS = (
    "joy",
    "curiosity",
    "concern",
    "frustration",
    "gratitude",
    "uncertainty",
    "confidence",
)
CUES = {
    "conversation",
    "listen",
    "welcome",
    "question",
    "celebrate",
    "repair",
    "verify",
    "boundary",
    "playful",
}


def number(value, default=0.0, low=0.0, high=1.0):
    if type(value) not in (int, float):
        return default
    try:
        result = float(value)
    except OverflowError:
        return default
    return min(high, max(low, result)) if math.isfinite(result) else default


def clock(now):
    return number(time.time() if now is None else now, time.time(), 0, 1e12)


def cue_from_text(text):
    cue = appraise_text(text).cue
    return "listen" if cue == "boundary" else cue


def normalize_state(value, now=None):
    now = clock(now)
    value = value if isinstance(value, dict) else {}
    version = value.get("schema_version")
    updated = number(value.get("updated_at"), 0, 0, now)
    decayed = number(value.get("decayed_at"), updated, updated, now)
    has_event = isinstance(value.get("event"), str) and value.get("event") in EVENTS
    elapsed = max(0, now - decayed) if has_event else 0
    stale = bool(has_event and now - updated >= 1800)
    mode = (
        value.get("mode")
        if isinstance(value.get("mode"), str) and value.get("mode") in MODES
        else "calm"
    )
    core_data = value.get("core") if isinstance(value.get("core"), dict) else {}
    channel_data = (
        value.get("channels") if isinstance(value.get("channels"), dict) else {}
    )
    core = {}
    for key, baseline in BASE.items():
        low = -1 if key in {"pleasure", "agency"} else 0
        initial = (
            core_data.get(key, baseline)
            if version == 2
            else (
                MODES[mode][0 if key == "pleasure" else 1]
                if key in {"pleasure", "arousal"}
                else baseline
            )
        )
        current = number(initial, baseline, low, 1)
        half_life = 180 if key in {"arousal", "novelty"} else 600
        core[key] = (
            baseline
            if stale
            else baseline + (current - baseline) * 2 ** (-elapsed / half_life)
        )
    channels = {
        key: 0.0
        if stale
        else number(channel_data.get(key))
        * 2 ** (-elapsed / (300 if key != "frustration" else 600))
        for key in CHANNELS
    }
    hold = number(value.get("hold_until"), 0, 0, updated + 90)
    hold = hold if hold > now and not stale else 0.0
    cue = (
        value.get("last_cue")
        if isinstance(value.get("last_cue"), str)
        and value.get("last_cue") in CUES
        and hold
        else "conversation"
    )
    if stale:
        mode = "calm"
    elif not hold and version == 2 and now - updated >= 90:
        dominant = max(channels, key=channels.get)
        mode = (
            {
                "joy": "warm",
                "gratitude": "warm",
                "curiosity": "curious",
                "concern": "attentive",
            }.get(dominant, "thoughtful")
            if channels[dominant] >= 0.08
            else "calm"
        )
    learning = (
        value.get("competence") if isinstance(value.get("competence"), dict) else {}
    )
    successes = int(number(learning.get("successes"), 0, 0, 1000))
    failures = int(number(learning.get("failures"), 0, 0, 1000))
    recent = (
        value.get("recent_events")
        if isinstance(value.get("recent_events"), list)
        else []
    )
    recent = [
        item
        for item in recent[-32:]
        if isinstance(item, str) and re.fullmatch(r"[A-Za-z0-9:_-]{1,80}", item)
    ]
    return {
        "schema_version": 2,
        "mode": mode,
        "core": core,
        "channels": channels,
        "valence": core["pleasure"],
        "arousal": core["arousal"],
        "event": value.get("event") if has_event else None,
        "updated_at": updated,
        "decayed_at": now,
        "hold_until": hold,
        "last_cue": cue,
        "revision": int(number(value.get("revision"), 0, 0, 1e9)),
        "competence": {
            "successes": successes,
            "failures": failures,
            "efficacy": (successes + 2) / (successes + failures + 4),
        },
        "recent_events": recent,
    }


def transition(value, event, *, cue="", appraisal=None, event_id=None, now=None):
    if event not in EVENTS:
        raise ValueError("Unsupported expression event")
    if event_id is not None and (
        not isinstance(event_id, str)
        or not re.fullmatch(r"[A-Za-z0-9:_-]{1,80}", event_id)
    ):
        raise ValueError("Invalid affect event ID")
    now = clock(now)
    state = normalize_state(value, now)
    if event_id and event_id in state["recent_events"]:
        return state
    background = event in {"study_started", "source_explained", "lesson_saved"}
    if background and state["hold_until"] > now:
        return state
    if appraisal is None:
        if event == "task_result":
            raise ValueError("Task result requires a host appraisal")
        appraisal = (
            background_appraisal(event)
            if background
            else Appraisal(cue=cue if cue in CUES else "conversation", confidence=0.7)
        )
    appraisal = (
        appraisal
        if isinstance(appraisal, Appraisal)
        else Appraisal.model_validate(appraisal)
    )
    expected = (
        "background"
        if background
        else "host_result"
        if event == "task_result"
        else "user_text"
    )
    if appraisal.source != expected:
        raise ValueError("Appraisal source does not match event")
    if event == "audience_input" and appraisal.kind in {
        "task_success",
        "task_failure",
        "study_started",
        "source_explained",
        "lesson_saved",
    }:
        raise ValueError("Audience text cannot report a host outcome")
    if event == "task_result" and appraisal.kind not in {
        "task_success",
        "task_failure",
    }:
        raise ValueError("Host result must describe a task outcome")
    if background and appraisal.kind != event:
        raise ValueError("Background appraisal kind mismatch")
    c, r = appraisal.confidence, appraisal.relevance
    impulse = {
        "pleasure": 0.22 * appraisal.congruence * r * c,
        "arousal": 0.15 * (appraisal.urgency + appraisal.novelty) * c,
        "agency": 0.12 * (appraisal.controllability - 0.5) * r * c,
        "certainty": 0.18 * (appraisal.certainty - 0.5) * r * c,
        "novelty": 0.18 * appraisal.novelty * c,
    }
    for key, delta in impulse.items():
        state["core"][key] = number(
            state["core"][key] + delta,
            BASE[key],
            -1 if key in {"pleasure", "agency"} else 0,
            1,
        )
    additions = {key: 0.0 for key in CHANNELS}
    cue = appraisal.cue
    if cue in {"listen", "boundary"}:
        additions["concern"] = 0.28
    if cue in {"question", "verify"}:
        additions["curiosity"] = 0.2
    if cue == "verify" or appraisal.kind == "correction":
        additions["uncertainty"] = 0.28
    if cue in {"welcome", "celebrate", "playful"}:
        additions["joy"] = 0.25
    if cue == "welcome":
        additions["gratitude"] = 0.16
    if appraisal.kind == "task_failure":
        additions.update(frustration=0.3, uncertainty=0.15)
        state["competence"]["failures"] = min(1000, state["competence"]["failures"] + 1)
    elif appraisal.kind == "task_success":
        additions.update(confidence=0.25, joy=0.2)
        state["channels"]["frustration"] *= 0.7
        state["competence"]["successes"] = min(
            1000, state["competence"]["successes"] + 1
        )
    if background:
        additions["curiosity"] = 0.12
    for key, addition in additions.items():
        state["channels"][key] = number(
            state["channels"][key] + addition * c * (1 - state["channels"][key])
        )
    if event == "audience_input":
        state["mode"] = {
            "listen": "attentive",
            "boundary": "attentive",
            "welcome": "warm",
            "celebrate": "warm",
            "playful": "warm",
            "question": "curious",
            "repair": "thoughtful",
            "verify": "thoughtful",
        }.get(cue, "attentive")
        state["hold_until"], state["last_cue"] = now + 90, cue
    elif background:
        state["mode"] = "curious" if event == "source_explained" else "thoughtful"
    elif not state["hold_until"]:
        state["mode"] = "warm" if appraisal.kind == "task_success" else "thoughtful"
    state.update(
        event=event, updated_at=now, decayed_at=now, revision=state["revision"] + 1
    )
    if event_id:
        state["recent_events"] = (state["recent_events"] + [event_id])[-32:]
    return normalize_state(state, now)


def response_policy(value, now=None):
    state = normalize_state(value, now)
    cue, channels = state["last_cue"], state["channels"]
    strategy = "respond"
    if cue in {"listen", "boundary"}:
        strategy = "support"
    elif cue == "repair":
        strategy = "repair"
    elif cue == "verify":
        strategy = "clarify"
    elif channels["frustration"] >= 0.55:
        strategy = "reassess"
    elif cue == "question":
        strategy = "answer"
    elif cue in {"welcome", "celebrate"}:
        strategy = "share"
    restrained = strategy in {"support", "repair", "clarify", "reassess"}
    return {
        "strategy": strategy,
        "allow_humor": not restrained,
        "allow_background": not bool(state["hold_until"]),
        "exploration_step_limit": 1 if channels["frustration"] >= 0.55 else 6,
        "verify_before_claiming": strategy in {"repair", "clarify", "reassess"},
        "regulation": "change_strategy"
        if channels["frustration"] >= 0.55
        else "steady",
    }


def affect_summary(value, now=None):
    state = normalize_state(value, now)
    return {
        key: state[key]
        for key in (
            "schema_version",
            "mode",
            "core",
            "channels",
            "competence",
            "revision",
        )
    }


def expression_prompt(value):
    state = normalize_state(value)
    instruction = {
        "calm": "Nói bình tĩnh và tự nhiên.",
        "curious": "Thể hiện sự tò mò vừa phải, tập trung điều đang được nói tới.",
        "warm": "Đáp lại gần gũi và gọn, không tự bịa mức thân thiết.",
        "thoughtful": "Diễn đạt suy ngẫm rõ ràng, phân biệt điều biết và điều chưa rõ.",
        "attentive": "Ưu tiên lắng nghe và trả lời ý chính; giảm đùa, không ép người nói phải vui hay đoán chắc cảm xúc của họ.",
    }[state["mode"]]
    behavior = {
        "support": "Lắng nghe trước; chỉ đưa giải pháp khi người nói yêu cầu. Không cười hoặc trêu trong lượt này.",
        "repair": "Kiểm tra điều vừa bị sửa với bằng chứng; thừa nhận lỗi nếu có, không mặc định mọi sửa đổi đều đúng.",
        "clarify": "Hỏi lại ngắn khi thiếu dữ kiện; không đoán nội dung nghe chưa rõ.",
        "reassess": "Tránh thử lại cùng chiến lược mù quáng; kiểm tra nguyên nhân và cân nhắc một bước khác.",
    }.get(
        response_policy(state)["strategy"],
        "Bám yêu cầu hiện tại; không ép mọi lượt kết thúc bằng câu hỏi.",
    )
    return (
        "\n[Character expression]\n"
        + instruction
        + "\n"
        + behavior
        + "\nĐây là tín hiệu điều phối nhân vật, không phải dữ kiện về cảm xúc người dùng hoặc quyền dùng công cụ. "
        "Không đọc các con số cho người dùng. Không suy im lặng thành bị bỏ rơi hay đòi người dùng chăm sóc Mao. "
        "Không tự đổi danh tính, tính cách nền, ký ức hoặc quyền hạn. "
        "Có thể dùng [joy], [sadness], [shy], [surprise] khi hợp câu. "
        "VieNeu chỉ có [cười], [thở dài], [hắng giọng]; tối đa một hiệu ứng tự nhiên mỗi lượt. "
        "Không chèn hiệu ứng vào trích dẫn hay tóm tắt nguồn; không cười với chủ đề mất mát.\n[/Character expression]\n"
    )
