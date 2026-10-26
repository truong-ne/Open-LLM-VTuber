"""Real-model Vietnamese retrieval, alias collision and abstention smoke benchmark."""

import argparse
import json
from pathlib import Path
import statistics
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.mao_hybrid import config  # noqa: E402
from src.open_llm_vtuber.agent.hybrid.store import Store  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keyword-only", action="store_true")
    args = parser.parse_args()
    settings = config().model_copy(
        update={"scope": "retrieval-eval-" + uuid.uuid4().hex, "embedding_timeout": 30}
    )
    dataset = json.loads(
        (ROOT / "tests/fixtures/mao_retrieval.vi.json").read_text(encoding="utf-8")
    )
    store = Store(settings)
    result = {
        "model": settings.embedding_model,
        "dimensions": settings.embedding_dimensions,
        "search_mode": settings.search_mode,
        "keyword_only": args.keyword_only,
        "dataset": "10 synthetic Vietnamese memories, 20 positive paraphrases, 6 unrelated queries; includes alias collisions and unaccented text",
        "queries": [],
        "negative_queries": [],
    }
    try:
        for memory in dataset["memories"]:
            store.remember(
                "long_term",
                "shared",
                memory["content"],
                "operator",
                public_alias=memory.get("alias"),
            )
            if store.embedding_status != "ready":
                raise RuntimeError(
                    "Actual embedding service unavailable; refusing fake semantic evaluation"
                )
        result["embedding_profile"] = store.embedding_profile
        with store.connect() as db:
            rows = db.execute(
                "SELECT id,content FROM mao_hybrid.memories WHERE scope=%s",
                (settings.scope,),
            ).fetchall()
        content_to_label = {m["content"]: m["id"] for m in dataset["memories"]}
        ids = {r["id"]: content_to_label[r["content"]] for r in rows}
        if args.keyword_only:
            store._vector = lambda *a, **kw: None
        for memory in dataset["memories"]:
            for query in memory["queries"]:
                start = time.perf_counter()
                ranked = [ids[r["id"]] for r in store.recall(query, limit=3)]
                rank = (
                    ranked.index(memory["id"]) + 1 if memory["id"] in ranked else None
                )
                result["queries"].append(
                    {
                        "expected": memory["id"],
                        "query": query,
                        "ranked": ranked,
                        "rank": rank,
                        "latency_ms": round((time.perf_counter() - start) * 1000, 1),
                    }
                )
        for query in dataset["negative_queries"]:
            rows = store.recall(query, limit=3)
            result["negative_queries"].append(
                {
                    "query": query,
                    "ranked": [ids[r["id"]] for r in rows],
                    "abstained": not rows,
                }
            )
        count = len(result["queries"])
        result["recall_at_3"] = (
            sum(q["rank"] is not None for q in result["queries"]) / count
        )
        result["top_1_accuracy"] = (
            sum(q["rank"] == 1 for q in result["queries"]) / count
        )
        result["mrr_at_3"] = (
            sum(1 / q["rank"] if q["rank"] else 0 for q in result["queries"]) / count
        )
        result["negative_abstention_rate"] = sum(
            q["abstained"] for q in result["negative_queries"]
        ) / len(result["negative_queries"])
        result["median_latency_ms"] = statistics.median(
            q["latency_ms"] for q in result["queries"]
        )
        name = (
            "mao-hybrid-retrieval-keyword.json"
            if args.keyword_only
            else "mao-hybrid-retrieval-eval.json"
        )
        (ROOT / "logs" / name).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    k: v
                    for k, v in result.items()
                    if k not in {"queries", "negative_queries"}
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        with store.connect() as db:
            db.execute(
                "DELETE FROM mao_hybrid.memories WHERE scope=%s", (settings.scope,)
            )
        store.close()


if __name__ == "__main__":
    main()
