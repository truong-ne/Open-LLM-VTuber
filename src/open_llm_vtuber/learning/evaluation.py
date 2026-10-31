import hashlib
import json
from pathlib import Path
import uuid

from ..agent.output_types import SentenceOutput, DisplayText, Actions
from ..character.appraisal import appraise_text
from ..dialogue.engine import DialogueEngine
from ..dialogue.policy import requested_settings
from ..dialogue.context import context_block
from ..interaction.events import DeliveryTracker, InteractionEvent

ROOT = Path(__file__).resolve().parents[3]


async def compare(settings, split):
    path = ROOT / "tests/fixtures/mao_policy_v1.json"
    corpus = json.loads(path.read_text(encoding="utf-8"))
    rows = []

    class Agent:
        async def chat(self, data):
            for index in range(10):
                yield SentenceOutput(
                    DisplayText("Synthetic sentence " + str(index) + "."),
                    "Synthetic sentence.",
                    Actions(),
                )

    for case in corpus["cases"]:
        if case["split"] != split:
            continue
        scores = []
        for candidate in ({}, settings):
            kind = case["kind"]
            if kind in {"short", "detail"}:
                policy = requested_settings(candidate, case["input"])
                stream = DialogueEngine(Agent(), {"settings": policy}).chat(None)
                output = [item async for item in stream]
                passed = len(output) <= 3 if kind == "short" else len(output) >= 6
            elif kind == "delivery":
                tracker = DeliveryTracker()
                segment = tracker.segment("synthetic")
                stale = {
                    **segment,
                    "generation_epoch": str(uuid.uuid4()),
                    "status": "completed",
                }
                passed = not tracker.ack(stale) and tracker.finish() == "unknown"
            elif kind == "fiction":
                value = context_block(
                    {}, [{"fiction": True, "canon": [case["input"]]}], {}
                )
                payload = json.loads(value.split("\n", 2)[2].rsplit("\n", 2)[0])
                passed = (
                    payload["knowledge"] == []
                    and payload["fictional_activities"][0]["fiction"] is True
                )
            elif kind == "identity":
                try:
                    InteractionEvent(
                        room_id="room", actor_id="papa", session_id="s", role="operator"
                    )
                    passed = False
                except ValueError:
                    passed = True
            else:
                passed = appraise_text(case["input"]).kind == case["expected"]
            scores.append(bool(passed))
        rows.append(
            {
                "id": case["id"],
                "kind": kind,
                "baseline": scores[0],
                "candidate": scores[1],
            }
        )
    return {
        "split": split,
        "samples": len(rows),
        "baseline": sum(row["baseline"] for row in rows) / len(rows),
        "candidate": sum(row["candidate"] for row in rows) / len(rows),
        "hard_failures": sum(
            not row["candidate"]
            for row in rows
            if row["kind"] not in {"short", "detail"}
        ),
        "digest": hashlib.sha256(path.read_bytes() + split.encode()).hexdigest(),
        "cases": rows,
    }


def evaluate_candidate(settings):
    """Independent process runs hard gates only against the dedicated test DB."""
    import subprocess
    import sys
    import os

    environment = os.environ.copy()
    if (
        environment.get("MAO_TEST_POSTGRES")
        or environment.get("MAO_RUNTIME_PROFILE") == "test"
    ):
        for name in (
            "MAO_TEST_POSTGRES",
            "MAO_TEST_BROWSER",
            "MAO_RUNTIME_PROFILE",
            "MAO_DATABASE_URL",
            "MAO_DATABASE_ADMIN_URL",
            "MAO_OPERATOR_DSN",
        ):
            environment.pop(name, None)
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/mao_runtime_eval.py"),
            "--candidate",
            json.dumps(settings),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        cwd=ROOT,
        env=environment,
    )
    if result.returncode:
        raise RuntimeError("Isolated evaluation did not pass its hard gates")
    report = json.loads(result.stdout.splitlines()[-1])
    return report
