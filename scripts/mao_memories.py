"""Read-only, scope-bound memory browsing for the local operator UI."""

import re

from mao_profile import profile_store
from src.open_llm_vtuber.agent.hybrid.store import normalize

PAGE_SIZE = 20
KINDS = {"long_term", "social", "skill"}
STATES = {"active", "expired", "all"}
FIELDS = (
    "id,kind,subject,public_alias,content,source,created::text,expires::text,"
    "expires<=now() AS expired,embedding IS NOT NULL AS has_embedding"
)


def parse_query(params):
    if set(params) - {"q", "kind", "state", "page"} or any(
        len(values) != 1 for values in params.values()
    ):
        raise ValueError("Unknown or repeated query parameter")
    query = params.get("q", [""])[0].strip()
    kind = params.get("kind", [""])[0]
    state = params.get("state", ["active"])[0]
    page = params.get("page", ["1"])[0]
    if (
        len(query) > 200
        or (kind and kind not in KINDS)
        or state not in STATES
        or not re.fullmatch(r"[1-9][0-9]{0,4}", page)
        or int(page) > 10000
    ):
        raise ValueError("Invalid memory filter")
    return {"query": query, "kind": kind, "state": state, "page": int(page)}


def serialize(row):
    return {**row, "id": str(row["id"])}


def list_memories(query="", kind="", state="active", page=1, *, store=None):
    # Validate programmatic callers too. Scope always comes from local config.
    options = parse_query(
        {"q": [query], "kind": [kind], "state": [state], "page": [str(page)]}
    )
    owned = store is None
    store = store or profile_store()
    try:
        where, values = ["scope=%s"], [store.scope]
        if options["state"] == "active":
            where.append("expires>now()")
        elif options["state"] == "expired":
            where.append("expires<=now()")
        if options["kind"]:
            where.append("kind=%s")
            values.append(options["kind"])
        if options["query"]:
            # Treat '%' and '_' literally; normalization supports Vietnamese
            # searches with or without accents without invoking an LLM/embedder.
            term = normalize(options["query"])
            term = term.replace("!", "!!").replace("%", "!%").replace("_", "!_")
            where.append("normalized ILIKE %s ESCAPE '!'")
            values.append("%" + term + "%")
        predicate = " AND ".join(where)
        with store.connect() as db:
            db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            summary = db.execute(
                "SELECT count(*) AS total,"
                "count(*) FILTER (WHERE expires>now()) AS active,"
                "count(*) FILTER (WHERE expires<=now()) AS expired "
                "FROM mao_hybrid.memories WHERE scope=%s",
                (store.scope,),
            ).fetchone()
            total = db.execute(
                "SELECT count(*) AS total FROM mao_hybrid.memories WHERE " + predicate,
                values,
            ).fetchone()["total"]
            pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
            page = min(options["page"], pages)
            rows = db.execute(
                "SELECT " + FIELDS + " FROM mao_hybrid.memories WHERE " + predicate
                + " ORDER BY created DESC,id DESC LIMIT %s OFFSET %s",
                [*values, PAGE_SIZE, (page - 1) * PAGE_SIZE],
            ).fetchall()
        return {
            "items": [serialize(row) for row in rows],
            "total": total,
            "page": page,
            "pages": pages,
            "page_size": PAGE_SIZE,
            "summary": summary,
        }
    finally:
        if owned:
            store.close()


def get_memory(memory_id, *, store=None):
    if not re.fullmatch(r"[1-9][0-9]{0,18}", str(memory_id)) or int(memory_id) > 2**63 - 1:
        raise ValueError("Invalid memory ID")
    owned = store is None
    store = store or profile_store()
    try:
        with store.connect() as db:
            db.execute("SET TRANSACTION READ ONLY")
            row = db.execute(
                "SELECT " + FIELDS + ",evidence,embedding_model "
                "FROM mao_hybrid.memories WHERE scope=%s AND id=%s",
                (store.scope, int(memory_id)),
            ).fetchone()
        return serialize(row) if row else None
    finally:
        if owned:
            store.close()
