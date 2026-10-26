"""Tool arguments are untrusted: validate them before any state or browser I/O."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Recall(Arguments):
    query: str = Field("", max_length=1000)
    kind: Literal["long_term", "social", "skill"] | None = None
    source: Literal["unverified_claim", "operator", "evaluation"] | None = None


class Remember(Arguments):
    kind: Literal["long_term", "social"]
    content: str = Field(min_length=3, max_length=1000)
    subject: str = Field("shared", min_length=1, max_length=80)


class Forget(Arguments):
    id: int = Field(gt=0)


class Feedback(Arguments):
    score: FiniteFloat = Field(ge=-1, le=1)
    note: str = Field("", max_length=500)


class PlanStep(Arguments):
    action: Literal["recall", "navigate", "observe", "screenshot"]
    query: str = Field("", max_length=500)
    url: str | None = Field(None, max_length=2000)
    expected_text: str | None = Field(None, min_length=2, max_length=200)


class Plan(Arguments):
    objective: str = Field(min_length=3, max_length=500)
    steps: list[PlanStep] = Field(min_length=1, max_length=6)


class Computer(Arguments):
    action: Literal[
        "navigate",
        "observe",
        "screenshot",
        "click",
        "fill",
        "vision_click",
        "scroll",
        "close",
    ]
    url: str | None = Field(None, max_length=2000)
    selector: str | None = Field(None, max_length=300)
    text: str | None = Field(None, max_length=2000)
    x: FiniteFloat | None = Field(None, ge=0, lt=1280)
    y: FiniteFloat | None = Field(None, ge=0, lt=720)
    observation: str | None = Field(None, max_length=64)
    dy: FiniteFloat | None = Field(None, ge=-720, le=720)


CONTRACTS = {
    "recall": Recall,
    "remember": Remember,
    "forget": Forget,
    "feedback": Feedback,
    "plan": Plan,
    "status": Arguments,
    "explore": Arguments,
    "cancel": Arguments,
    "computer": Computer,
}


def validate(operation, data):
    if operation not in CONTRACTS:
        raise ValueError("Unknown hybrid operation")
    result = CONTRACTS[operation].model_validate(data).model_dump(exclude_none=True)
    if operation == "computer":
        required = {
            "navigate": ("url",),
            "click": ("selector", "observation"),
            "fill": ("selector", "text", "observation"),
            "vision_click": ("x", "y", "observation"),
            "scroll": ("dy", "observation"),
        }.get(result["action"], ())
        if any(key not in result for key in required):
            raise ValueError("Missing required fields for computer action")
        allowed = {"action", *required}
        if set(result) - allowed:
            raise ValueError("Unexpected fields for computer action")
    return result
