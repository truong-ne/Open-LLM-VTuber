"""Bounded game-only observations; no model self-rating or persona changes."""

from .wesnoth import SESSION, read_json, write_json

OUTCOMES = {"victory", "defeat", "turn_limit"}
LESSONS = {
    "unused_options": (
        "Previous games ended turns with attack or recruit options still available. "
        "Compare those options before ending a turn; availability does not make them good moves."
    ),
    "leader_risk": (
        "Previous games included leader attacks with forecast death probability at least 25%. "
        "Check the combat forecast and safer alternatives before risking the leader."
    ),
}


def load_reviews(directory):
    try:
        records = read_json(directory / "reviews.json")
    except (OSError, ValueError):
        return []
    if not isinstance(records, list):
        return []
    return [
        r
        for r in records[-20:]
        if isinstance(r, dict)
        and SESSION.fullmatch(str(r.get("session", "")))
        and r.get("outcome") in OUTCOMES
        and all(type(r.get(k)) is int and 0 <= r[k] <= 288 for k in LESSONS)
    ]


def lesson_codes(records):
    return [key for key in LESSONS if any(r.get(key, 0) > 0 for r in records)]


class GameReview:
    def __init__(self, session):
        self.session = session
        self.counts = dict.fromkeys(LESSONS, 0)
        self.confirmed_actions = 0
        self.seen = set()

    def record(self, before, result):
        request = result.get("request_id")
        if (
            before is None
            or result.get("session") != self.session
            or before.get("session") != self.session
            or before.get("request_id") != request
            or result.get("confirmed") is not True
            or result.get("status") != "completed"
            or request in self.seen
            or len(self.seen) >= 288
        ):
            return
        action = next(
            (
                a
                for a in before.get("actions", [])
                if a.get("id") == result.get("action_id")
            ),
            None,
        )
        if action is None:
            return
        self.seen.add(request)
        self.confirmed_actions += 1
        if action.get("kind") == "end_turn" and any(
            a.get("kind") in {"attack", "recruit"} for a in before.get("actions", [])
        ):
            self.counts["unused_options"] += 1
        unit = next(
            (u for u in before.get("units", []) if u.get("id") == action.get("unit")),
            {},
        )
        risk = action.get("forecast", {}).get("attacker_death_probability", 0)
        if (
            action.get("kind") == "attack"
            and unit.get("leader") is True
            and type(risk) in (int, float)
            and 0.25 <= risk <= 1
        ):
            self.counts["leader_risk"] += 1

    def finish(self, event, directory):
        if event.get("session") != self.session or event.get("outcome") not in OUTCOMES:
            raise ValueError("Invalid game outcome")
        report = {
            "session": self.session,
            "outcome": event["outcome"],
            "confirmed_actions": self.confirmed_actions,
            **self.counts,
            "quality_improvement_verified": False,
        }
        records = load_reviews(directory)
        records = [r for r in records if r["session"] != self.session]
        write_json(directory / "reviews.json", (records + [report])[-20:])
        return report


def describe_outcome(state):
    speech = {
        "victory": "Mao thắng trận tập này rồi!",
        "defeat": "Mao thua trận tập này rồi.",
        "turn_limit": "Trận tập đã hết số lượt; Mao chưa được xác nhận thắng.",
    }[state["outcome"]]
    review = state.get("review", {})
    if review.get("unused_options", 0):
        speech += " Có lượt thiếp kết thúc khi vẫn còn lựa chọn tấn công hoặc tuyển quân; lần sau thiếp sẽ cân nhắc kỹ hơn."
    elif review.get("leader_risk", 0):
        speech += " Thiếp đã chọn đòn đánh có rủi ro cao cho đội trưởng; lần sau cần xem kỹ dự báo giao tranh."
    return speech
