"""Review real game evidence; optionally ask local Qwen for an unverified hypothesis."""

import argparse
from collections import Counter
import json
import statistics
import sys

import httpx

from mao_hybrid import ROOT, config, Store


def review_games(reflect=False):
    settings = config()
    game_store = Store(settings.model_copy(update={"scope": "mao-game-2048"}))
    memory_store = Store(settings)
    try:
        history = game_store.get("2048_runs", [])
        verified = [r for r in history if r.get("verified") is True]
        # Never compare a short scene showcase with a full learning trial.
        budgets = Counter(r["max_moves"] for r in verified)
        budget = budgets.most_common(1)[0][0] if budgets else None
        comparison = [
            r
            for r in verified
            if r["max_moves"] == budget
            and r.get("outcome") in {"game_over", "won", "move_budget"}
        ]
        means = {
            p: round(
                statistics.mean(r["score"] for r in comparison if r["policy"] == p), 1
            )
            for p in ("merge", "corner")
            if any(r["policy"] == p for r in comparison)
        }
        report = {
            "source": "https://2048game.com/",
            "real_website": True,
            "verified_runs": len(verified),
            "verified_moves": sum(r["moves"] for r in verified),
            "best_score": max((r["score"] for r in verified), default=0),
            "comparison_max_moves": budget,
            "comparison_runs": len(comparison),
            "runs": verified,
            "mean_scores": means,
            "strategy": game_store.get("2048_strategy", {}),
            "quality_improvement_verified": False,
            "reflection_status": "not_requested",
        }
        if reflect and verified:
            try:
                response = httpx.post(
                    "http://127.0.0.1:11434/api/chat",
                    json={
                        "model": "mao-companion",
                        "think": False,
                        "stream": False,
                        "format": "json",
                        "keep_alive": "60s",
                        "options": {
                            "num_ctx": 2048,
                            "num_predict": 220,
                            "temperature": 0.2,
                        },
                        "messages": [
                            {
                                "role": "system",
                                "content": 'Chỉ phân tích dữ liệu game được cung cấp. Viết JSON {"hypothesis":"..."} tối đa 70 từ, không đặt danh tính hoặc cách xưng hô của nhân vật. Nêu một giả thuyết cải thiện cần thử. Không tuyên bố đã tiến bộ, không tạo lệnh, không thay quyền, không tự chấm thành tích.',
                            },
                            {
                                "role": "user",
                                "content": json.dumps(report, ensure_ascii=False),
                            },
                        ],
                    },
                    timeout=90,
                    trust_env=False,
                )
                response.raise_for_status()
                hypothesis = json.loads(response.json()["message"]["content"]).get(
                    "hypothesis"
                )
                if not isinstance(hypothesis, str) or not hypothesis.strip():
                    raise ValueError("Missing hypothesis")
                report.update(
                    reflection_status="local_qwen_hypothesis",
                    hypothesis=hypothesis[:500],
                    hypothesis_verified=False,
                )
            except (httpx.HTTPError, ValueError, KeyError):
                report["reflection_status"] = "unavailable_no_claim_of_learning"
        if verified:
            content = json.dumps(
                {
                    "game": "2048",
                    "real_games": len(verified),
                    "moves": report["verified_moves"],
                    "best_score": report["best_score"],
                    "mean_scores": means,
                    "comparison_max_moves": budget,
                    "strategy": report["strategy"].get("policy"),
                    "hypothesis": report.get("hypothesis", "")[:300],
                    "hypothesis_verified": False,
                },
                ensure_ascii=False,
            )
            memory_store.remember(
                "skill",
                "shared",
                content,
                "evaluation",
                evidence="Real Chrome game; independently checked arrow transitions and DOM scores. Source: https://2048game.com/. Run ids: "
                + ",".join(r["id"] for r in verified[-6:]),
            )
            report["embedding_status"] = memory_store.embedding_status
            report["saved_to_mao_skill_memory"] = True
        (ROOT / "logs/mao-game-review.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return report
    finally:
        game_store.close()
        memory_store.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reflect", action="store_true")
    args = parser.parse_args()
    print(json.dumps(review_games(args.reflect), ensure_ascii=False, indent=2))
