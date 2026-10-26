"""A bounded planner and evidence ledger, not a replacement game or game UI.

The driver reads the real game's visible tiles and sends arrow keys. Rule
prediction verifies effects; only real website scores enter the learning gate.
"""

from collections import defaultdict
from datetime import datetime, timezone
import math
import re
import statistics

from psycopg.types.json import Jsonb

URL = "https://2048game.com/"
KEYS = {
    "up": "ArrowUp",
    "left": "ArrowLeft",
    "down": "ArrowDown",
    "right": "ArrowRight",
}
POLICIES = ("merge", "corner")


def board_from_tiles(tiles):
    board = [0] * 16
    for tile in tiles:
        position = re.search(r"\btile-position-([1-4])-([1-4])\b", tile["classes"])
        value = int(tile["value"])
        if not position or value < 2 or value > 131072 or value & (value - 1):
            raise ValueError("Invalid visible tile")
        index = (int(position[2]) - 1) * 4 + int(position[1]) - 1
        # During a merge the old and new elements briefly share one position.
        board[index] = max(board[index], value)
    if sum(v > 0 for v in board) < 2:
        raise ValueError("Visible board is not ready")
    return tuple(board)


def move(board, direction):
    if len(board) != 16 or direction not in KEYS:
        raise ValueError("Invalid board or direction")
    result = list(board)
    gain = 0
    for line in range(4):
        indices = (
            [line * 4 + i for i in range(4)]
            if direction in {"left", "right"}
            else [i * 4 + line for i in range(4)]
        )
        if direction in {"right", "down"}:
            indices.reverse()
        values = [board[i] for i in indices if board[i]]
        merged = []
        index = 0
        while index < len(values):
            if index + 1 < len(values) and values[index] == values[index + 1]:
                value = values[index] * 2
                merged.append(value)
                gain += value
                index += 2
            else:
                merged.append(values[index])
                index += 1
        for index, value in zip(indices, merged + [0] * (4 - len(merged))):
            result[index] = value
    return tuple(result), gain


def verified_transition(before, after, direction, previous_score, score):
    predicted, gain = move(before, direction)
    if predicted == before or score != previous_score + gain:
        return False
    changed = [i for i in range(16) if after[i] != predicted[i]]
    return (
        len(changed) == 1 and predicted[changed[0]] == 0 and after[changed[0]] in {2, 4}
    )


def evaluate(board, policy):
    empty = board.count(0)
    logs = [math.log2(v) if v else 0 for v in board]
    if policy == "merge":
        return empty * 12 + sum(logs)
    maximum = max(board)
    # A fixed bottom-left corner and smoothly decreasing rows encourage space.
    snake = (4, 3, 2, 1, 5, 6, 7, 8, 12, 11, 10, 9, 16, 15, 14, 13)
    smooth = sum(
        abs(logs[r * 4 + c] - logs[r * 4 + c + 1]) for r in range(4) for c in range(3)
    )
    smooth += sum(
        abs(logs[r * 4 + c] - logs[(r + 1) * 4 + c]) for r in range(3) for c in range(4)
    )
    return (
        empty * 30
        + sum(v * w for v, w in zip(logs, snake)) * 0.65
        - smooth * 1.5
        + (50 if board[12] == maximum else 0)
    )


def choose(board, policy):
    if policy not in POLICIES:
        raise ValueError("Unrecognized strategy")
    choices = []
    for direction in ("down", "left", "right", "up"):
        next_board, gain = move(board, direction)
        if next_board == board:
            continue
        utility = evaluate(next_board, policy) + math.log2(gain + 1) * (
            5 if policy == "merge" else 2
        )
        if policy == "corner":
            # One bounded look-ahead. The random spawn is not read or predicted.
            futures = [
                evaluate(future, policy)
                for action in KEYS
                if (future := move(next_board, action)[0]) != next_board
            ]
            if futures:
                utility += max(futures) * 0.25
        choices.append((utility, direction))
    return max(choices, key=lambda item: item[0])[1] if choices else None


def promotion(history, current, max_moves):
    samples = defaultdict(list)
    for run in history:
        if (
            run.get("verified") is True
            and run.get("max_moves") == max_moves
            and run.get("outcome") in {"game_over", "won", "move_budget"}
            and run.get("policy") in POLICIES
        ):
            samples[run["policy"]].append(run["score"])
    if any(len(samples[p]) < 3 for p in POLICIES):
        return current, "insufficient_real_games"
    means = {p: statistics.mean(samples[p][-5:]) for p in POLICIES}
    candidate = max(means, key=means.get)
    if candidate != current and means[candidate] > means[current] * 1.1:
        return candidate, "better_mean_in_small_real_game_sample"
    return current, "keep_current"


class GameLedger:
    def __init__(self, store):
        self.store = store
        self.scope = store.scope

    def champion(self):
        value = self.store.get("2048_strategy", {"policy": "merge", "version": 0})
        return (
            value
            if value.get("policy") in POLICIES
            else {"policy": "merge", "version": 0}
        )

    def finish(self, run):
        # Accept only the driver's fixed numeric record, never text from the page.
        clean = {
            k: run[k]
            for k in (
                "id",
                "policy",
                "score",
                "moves",
                "max_tile",
                "max_moves",
                "outcome",
                "verified",
            )
        }
        if (
            clean["policy"] not in POLICIES
            or type(clean["score"]) is not int
            or clean["score"] < 0
        ):
            raise ValueError("Invalid run evidence")
        clean["at"] = datetime.now(timezone.utc).isoformat()
        with self.store.connect() as db:
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                ("game2048:" + self.scope,),
            )
            rows = db.execute(
                "SELECT key,value FROM mao_hybrid.state WHERE scope=%s AND key IN ('2048_runs','2048_strategy')",
                (self.scope,),
            ).fetchall()
            state = {r["key"]: r["value"] for r in rows}
            history = state.get("2048_runs", [])
            if any(item["id"] == clean["id"] for item in history):
                return state.get("2048_strategy", {"policy": "merge", "version": 0})
            history = (history + [clean])[-40:]
            current = state.get("2048_strategy", {"policy": "merge", "version": 0})
            policy, reason = promotion(history, current["policy"], clean["max_moves"])
            profile = {
                "policy": policy,
                "version": current["version"] + int(policy != current["policy"]),
                "reason": reason,
                "quality_improvement_verified": False,
            }
            for key, value in (("2048_runs", history), ("2048_strategy", profile)):
                db.execute(
                    "INSERT INTO mao_hybrid.state(scope,key,value) VALUES(%s,%s,%s) ON CONFLICT(scope,key) DO UPDATE SET value=excluded.value",
                    (self.scope, key, Jsonb(value)),
                )
        self.store.event("game2048_completed", clean)
        return profile
