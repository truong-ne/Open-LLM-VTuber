"""Pooled PostgreSQL/pgvector I/O, used in worker threads, with no SQLite fallback."""

import hashlib
import json
import math
import os
import re
import unicodedata
import uuid
from pathlib import Path
from urllib.parse import urljoin

import httpx

ROOT = Path(__file__).resolve().parents[4]


def normalize(text):
    return "".join(
        c
        for c in unicodedata.normalize("NFD", text.casefold())
        if unicodedata.category(c) != "Mn"
    ).replace("đ", "d")


def lexical_query(text):
    # PostgreSQL simple dictionary does not provide Vietnamese stop-word removal.
    # OR over content terms avoids an all-words-required query on long spoken input.
    stop = set(
        "mao minh ban toi la thi va cua co khong cho voi nay do mot nhung cac o trong khi nen the nao gi ai dau de vao ra duoc nguoi thuong".split()
    )
    terms = [
        term
        for term in dict.fromkeys(re.findall(r"\w+", normalize(text)))
        if term not in stop
    ]
    return " OR ".join(terms[:16])


def resolve_dsn(config):
    dsn = os.environ.get(config.database_url_env)
    path = Path(config.database_env_file)
    if not path.is_absolute():
        path = ROOT / path
    if not dsn and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == config.database_url_env:
                dsn = value.strip().strip('"').strip("'")
    if not dsn:
        raise RuntimeError("PostgreSQL is not configured; run Mao hybrid setup")
    return dsn


class OllamaEmbedder:
    def __init__(self, config):
        self.config = config
        self.profile = None

    def _digest(self, client):
        response = client.get(urljoin(self.config.embedding_url, "tags"))
        response.raise_for_status()
        expected = self.config.embedding_model
        expected = expected if ":" in expected else expected + ":latest"
        model = next(
            (m for m in response.json()["models"] if m["name"] == expected), None
        )
        if not model or not re.fullmatch(
            r"(?:sha256:)?[0-9a-f]{64}", model.get("digest", "")
        ):
            raise ValueError("Installed embedding model/digest not found")
        digest = model["digest"]
        if self.config.embedding_digest and digest != self.config.embedding_digest:
            raise ValueError("Installed embedding digest differs from the operator pin")
        return digest

    def ensure_profile(self):
        with httpx.Client(
            timeout=self.config.embedding_timeout, trust_env=False
        ) as client:
            digest = self._digest(client)
        self.profile = (
            f"{self.config.embedding_model}@{digest}:{self.config.embedding_dimensions}"
        )
        return self.profile

    def embed(self, text, query=False):
        if query:
            text = (
                "Instruct: Retrieve relevant memories about the user, preferences and evaluated skills.\nQuery: "
                + text
            )
        with httpx.Client(
            timeout=self.config.embedding_timeout, trust_env=False
        ) as client:
            before = self._digest(client)
            response = client.post(
                self.config.embedding_url,
                json={
                    "model": self.config.embedding_model,
                    "input": text[:8000],
                    "dimensions": self.config.embedding_dimensions,
                    "truncate": False,
                    "keep_alive": "5m",
                },
            )
            response.raise_for_status()
            vector = response.json()["embeddings"][0]
            if self._digest(client) != before:
                raise ValueError("Embedding model changed while producing a vector")
        if len(vector) != self.config.embedding_dimensions or not all(
            math.isfinite(float(v)) for v in vector
        ):
            raise ValueError("Embedding profile mismatch")
        if not any(float(v) for v in vector):
            raise ValueError("Zero embedding")
        self.profile = (
            f"{self.config.embedding_model}@{before}:{self.config.embedding_dimensions}"
        )
        return vector


class Store:
    def __init__(self, config, embedder=None):
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        self.config, self.scope = config, config.scope
        self.embedder = embedder or OllamaEmbedder(config)
        self.embedding_status = "not_checked"
        self.pool = ConnectionPool(
            resolve_dsn(config),
            min_size=0,
            max_size=4,
            timeout=5,
            open=False,
            kwargs={
                "row_factory": dict_row,
                "connect_timeout": 4,
                "options": "-c statement_timeout=5000 -c lock_timeout=3000",
            },
        )
        self.pool.open()

    def connect(self):
        return self.pool.connection()

    def migrate(self):
        with self.connect() as db:
            db.execute("SELECT pg_advisory_xact_lock(742019103)")
            for path in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
                db.execute(path.read_text(encoding="utf-8"))

    @property
    def embedding_profile(self):
        return getattr(self.embedder, "profile", None) or self.config.embedding_model

    def _vector(self, text, query=False):
        try:
            vector = self.embedder.embed(text, query=query)
            self.embedding_status = "ready"
            return json.dumps([float(v) for v in vector])
        except (httpx.HTTPError, KeyError, IndexError, ValueError):
            self.embedding_status = "unavailable_keyword_only"
            return None

    def remember(
        self,
        kind,
        subject,
        content,
        source="unverified_claim",
        *,
        public_alias=None,
        evidence=None,
    ):
        if kind not in {"long_term", "social", "skill"} or source not in {
            "unverified_claim",
            "operator",
            "evaluation",
        }:
            raise ValueError("Unknown memory kind/provenance")
        content = str(content).strip()[:1000]
        if not content:
            raise ValueError("Empty memory")
        if re.search(
            r"(?i)(?:password|api[_ -]?key|bearer|mat khau|secret|token)\s*[:=]\s*\S+|\bsk-[A-Za-z0-9]{16,}",
            normalize(content),
        ):
            raise ValueError("Credential-like content cannot be stored as memory")
        subject = str(subject)[:100]
        vector = self._vector(str(public_alias or subject) + ": " + content)
        with self.connect() as db:
            db.execute(
                """INSERT INTO mao_hybrid.memories
                (scope,kind,subject,content,normalized,source,embedding,embedding_model,expires,public_alias,alias_normalized,evidence)
                VALUES(%s,%s,%s,%s,%s,%s,%s::vector,%s,now()+%s*interval '1 day',%s,%s,%s)
                ON CONFLICT(scope,kind,subject,(coalesce(alias_normalized,'')),content_hash) DO NOTHING""",
                (
                    self.scope,
                    kind,
                    subject,
                    content,
                    normalize(str(public_alias or subject) + " " + content),
                    source,
                    vector,
                    self.embedding_profile if vector else None,
                    self.config.retention_days,
                    str(public_alias)[:80] if public_alias else None,
                    normalize(str(public_alias))[:80] if public_alias else None,
                    str(evidence)[:1000] if evidence else None,
                ),
            )
            db.execute(
                "DELETE FROM mao_hybrid.memories WHERE scope=%s AND expires<now()",
                (self.scope,),
            )
            db.execute(
                """DELETE FROM mao_hybrid.memories WHERE scope=%s AND id NOT IN
                (SELECT id FROM mao_hybrid.memories WHERE scope=%s ORDER BY id DESC LIMIT %s)""",
                (self.scope, self.scope, self.config.memory_limit),
            )

    def recall(self, query="", subject=None, limit=6, kind=None, source=None):
        query = str(query).strip()[:1000]
        vector = self._vector(query, query=True) if query else None
        params = {
            "scope": self.scope,
            "subject": subject,
            "kind": kind,
            "source": source,
            "query": normalize(query),
            "fts_query": lexical_query(query),
            "vector": vector,
            "model": self.embedding_profile,
            "limit": max(1, min(10, limit)),
            "min_similarity": self.config.minimum_similarity,
            "aliases": None,
            "terms": lexical_query(query).split(" OR ") if lexical_query(query) else [],
        }
        where = """scope=%(scope)s AND expires>now()
            AND (subject='shared' OR subject=%(subject)s)
            AND (%(kind)s::text IS NULL OR kind=%(kind)s)
            AND (%(source)s::text IS NULL OR source=%(source)s)"""
        where += " AND (%(aliases)s::text[] IS NULL OR public_alias IS NULL OR alias_normalized=ANY(%(aliases)s))"
        with self.connect() as db:
            if query:
                aliases = db.execute(
                    "SELECT DISTINCT alias_normalized FROM mao_hybrid.memories WHERE scope=%s AND expires>now() AND alias_normalized IS NOT NULL",
                    (self.scope,),
                ).fetchall()
                matched = [
                    r["alias_normalized"]
                    for r in aliases
                    if re.search(
                        r"(?<!\w)" + re.escape(r["alias_normalized"]) + r"(?!\w)",
                        normalize(query),
                    )
                ]
                params["aliases"] = matched or None
            params["minimum_overlap"] = (
                1
                if len(params["terms"]) <= 3 or params["aliases"]
                else self.config.lexical_min_overlap
            )
            params["short_query"] = len(params["terms"]) <= 3
            if self.config.search_mode == "ann":
                db.execute("SET LOCAL hnsw.iterative_scan = strict_order")
                db.execute("SET LOCAL hnsw.ef_search = 100")
            else:
                db.execute("SET LOCAL enable_indexscan = off")
            if not query:
                rows = db.execute(
                    "SELECT id,kind,subject,content,source,public_alias,evidence,extract(epoch from created)::float8 AS created_at FROM mao_hybrid.memories WHERE "
                    + where
                    + " ORDER BY id DESC LIMIT %(limit)s",
                    params,
                ).fetchall()
            else:
                rows = db.execute(
                    """
                    WITH semantic_candidates AS MATERIALIZED (
                        SELECT id, embedding <=> %(vector)s::vector AS distance
                        FROM mao_hybrid.memories WHERE """
                    + where
                    + """
                          AND embedding IS NOT NULL AND embedding_model=%(model)s
                          AND %(vector)s::vector IS NOT NULL
                        ORDER BY embedding <=> %(vector)s::vector LIMIT 30
                    ), semantic AS (
                        SELECT id, row_number() OVER(ORDER BY distance,id) AS rank
                        FROM semantic_candidates WHERE distance <= 1-%(min_similarity)s
                    ), lexical_candidates AS (
                        SELECT id, ts_rank_cd(search,websearch_to_tsquery('simple',%(fts_query)s))
                            + similarity(normalized,%(query)s) AS score
                        FROM mao_hybrid.memories WHERE """
                    + where
                    + """
                          AND ((search @@ websearch_to_tsquery('simple',%(fts_query)s)
                                AND (SELECT count(*) FROM unnest(tsvector_to_array(search)) AS token
                                     WHERE token=ANY(%(terms)s)) >= %(minimum_overlap)s)
                               OR (%(short_query)s AND normalized %% %(query)s))
                        ORDER BY score DESC,id LIMIT 30
                    ), lexical AS (
                        SELECT id,row_number() OVER(ORDER BY score DESC,id) AS rank FROM lexical_candidates
                    ), fused AS (
                        SELECT coalesce(s.id,l.id) AS id,
                            coalesce(1.0/(60+s.rank),0)+coalesce(1.2/(60+l.rank),0) AS score
                        FROM semantic s FULL JOIN lexical l ON s.id=l.id
                    ) SELECT m.id,m.kind,m.subject,m.content,m.source,m.public_alias,m.evidence,
                             extract(epoch from m.created)::float8 AS created_at,f.score
                      FROM fused f JOIN mao_hybrid.memories m ON m.id=f.id
                      ORDER BY f.score DESC,m.id DESC LIMIT %(limit)s
                """,
                    params,
                ).fetchall()
        return [
            dict(r, score=float(r["score"])) if "score" in r else dict(r) for r in rows
        ]

    def reembed(self, batch=50):
        if hasattr(self.embedder, "ensure_profile"):
            self.embedder.ensure_profile()
        with self.connect() as db:
            rows = db.execute(
                """SELECT id,subject,content,public_alias FROM mao_hybrid.memories
                WHERE scope=%s AND expires>now() AND (embedding IS NULL OR embedding_model<>%s)
                ORDER BY id LIMIT %s""",
                (self.scope, self.embedding_profile, batch),
            ).fetchall()
        count = 0
        for row in rows:
            vector = self._vector(
                (row["public_alias"] or row["subject"]) + ": " + row["content"]
            )
            if vector is None:
                break
            with self.connect() as db:
                db.execute(
                    "UPDATE mao_hybrid.memories SET embedding=%s::vector,embedding_model=%s WHERE scope=%s AND id=%s",
                    (vector, self.embedding_profile, self.scope, row["id"]),
                )
            count += 1
        return count

    def forget(self, memory_id):
        with self.connect() as db:
            db.execute(
                "DELETE FROM mao_hybrid.memories WHERE scope=%s AND id=%s",
                (self.scope, int(memory_id)),
            )

    def get(self, key, default=None):
        with self.connect() as db:
            row = db.execute(
                "SELECT value FROM mao_hybrid.state WHERE scope=%s AND key=%s",
                (self.scope, key),
            ).fetchone()
        return row["value"] if row else default

    def put(self, key, value):
        from psycopg.types.json import Jsonb

        with self.connect() as db:
            db.execute(
                """INSERT INTO mao_hybrid.state VALUES(%s,%s,%s)
                ON CONFLICT(scope,key) DO UPDATE SET value=excluded.value""",
                (self.scope, key, Jsonb(value)),
            )

    def event(self, kind, data):
        from psycopg.types.json import Jsonb

        with self.connect() as db:
            db.execute(
                "INSERT INTO mao_hybrid.events(scope,kind,data) VALUES(%s,%s,%s)",
                (self.scope, kind, Jsonb(data)),
            )
            db.execute(
                """DELETE FROM mao_hybrid.events WHERE scope=%s AND id NOT IN
                (SELECT id FROM mao_hybrid.events WHERE scope=%s ORDER BY id DESC LIMIT 5000)""",
                (self.scope, self.scope),
            )
            db.execute("DELETE FROM mao_hybrid.approvals WHERE expires<now()")

    def rate_limit(self, limit):
        with self.connect() as db:
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("rate:" + self.scope,),
            )
            count = db.execute(
                "SELECT count(*) AS n FROM mao_hybrid.events WHERE scope=%s AND kind='computer_attempt' AND created>now()-interval '1 minute'",
                (self.scope,),
            ).fetchone()["n"]
            if count >= limit:
                raise PermissionError("Computer rate limit reached; wait one minute")
            db.execute(
                "INSERT INTO mao_hybrid.events(scope,kind,data) VALUES(%s,'computer_attempt','{}')",
                (self.scope,),
            )

    def claim_goal(self, seconds):
        from psycopg.types.json import Jsonb

        with self.connect() as db:
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("goal:" + self.scope,),
            )
            rows = db.execute(
                "SELECT key,value FROM mao_hybrid.state WHERE scope=%s AND key IN ('goal','last_exploration','exploration_lease')",
                (self.scope,),
            ).fetchall()
            state = {r["key"]: r["value"] for r in rows}
            goal = state.get("goal")
            now = db.execute(
                "SELECT extract(epoch FROM clock_timestamp())::float8 AS now"
            ).fetchone()["now"]
            if goal and goal["status"] == "running":
                if state.get("exploration_lease", 0) > now:
                    return {"status": "busy"}
                goal["status"] = "stopped"
                goal["error"] = "previous process interrupted; create a new plan"
                db.execute(
                    "UPDATE mao_hybrid.state SET value=%s WHERE scope=%s AND key='goal'",
                    (Jsonb(goal), self.scope),
                )
                return {"status": "stopped"}
            if not goal or goal["status"] != "planned":
                return {"status": "no_pending_goal"}
            if now - state.get("last_exploration", 0) < 60:
                return {"status": "cooldown"}
            goal["status"] = "running"
            goal["lease_id"] = uuid.uuid4().hex
            for key, value in (
                ("goal", goal),
                ("last_exploration", now),
                ("exploration_lease", now + seconds + 10),
            ):
                db.execute(
                    "INSERT INTO mao_hybrid.state VALUES(%s,%s,%s) ON CONFLICT(scope,key) DO UPDATE SET value=excluded.value",
                    (self.scope, key, Jsonb(value)),
                )
            return {"status": "claimed", "goal": goal}

    def create_goal(self, goal):
        from psycopg.types.json import Jsonb

        with self.connect() as db:
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("goal:" + self.scope,),
            )
            row = db.execute(
                "SELECT value FROM mao_hybrid.state WHERE scope=%s AND key='goal'",
                (self.scope,),
            ).fetchone()
            if row and row["value"]["status"] in {"planned", "running"}:
                raise ValueError(
                    "Finish or cancel the current goal before replacing it"
                )
            db.execute(
                "INSERT INTO mao_hybrid.state VALUES(%s,'goal',%s) ON CONFLICT(scope,key) DO UPDATE SET value=excluded.value",
                (self.scope, Jsonb(goal)),
            )

    def goal_is_current(self, goal):
        with self.connect() as db:
            row = db.execute(
                """SELECT g.value AS goal,l.value AS lease,
                extract(epoch FROM clock_timestamp())::float8 AS now
                FROM mao_hybrid.state g JOIN mao_hybrid.state l ON l.scope=g.scope AND l.key='exploration_lease'
                WHERE g.scope=%s AND g.key='goal'""",
                (self.scope,),
            ).fetchone()
        return bool(
            row
            and row["goal"].get("id") == goal.get("id")
            and row["goal"].get("lease_id") == goal.get("lease_id")
            and row["goal"]["status"] == "running"
            and row["lease"] > row["now"]
        )

    def save_goal(self, goal):
        from psycopg.types.json import Jsonb

        with self.connect() as db:
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("goal:" + self.scope,),
            )
            row = db.execute(
                "SELECT value FROM mao_hybrid.state WHERE scope=%s AND key='goal' FOR UPDATE",
                (self.scope,),
            ).fetchone()
            if (
                not row
                or row["value"].get("id") != goal.get("id")
                or row["value"].get("lease_id") != goal.get("lease_id")
                or row["value"]["status"] != "running"
            ):
                return False
            db.execute(
                "UPDATE mao_hybrid.state SET value=%s WHERE scope=%s AND key='goal'",
                (Jsonb(goal), self.scope),
            )
            return True

    def cancel_goal(self):
        from psycopg.types.json import Jsonb

        with self.connect() as db:
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("goal:" + self.scope,),
            )
            row = db.execute(
                "SELECT value FROM mao_hybrid.state WHERE scope=%s AND key='goal' FOR UPDATE",
                (self.scope,),
            ).fetchone()
            goal = row["value"] if row else None
            if goal and goal["status"] in {
                "planned",
                "running",
                "needs_operator",
                "needs_revision",
            }:
                goal["status"] = "cancelled"
                db.execute(
                    "UPDATE mao_hybrid.state SET value=%s WHERE scope=%s AND key='goal'",
                    (Jsonb(goal), self.scope),
                )
            return goal

    def adjust_traits(self, score, note):
        from psycopg.types.json import Jsonb

        with self.connect() as db:
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("traits:" + self.scope,),
            )
            row = db.execute(
                "SELECT value FROM mao_hybrid.state WHERE scope=%s AND key='traits'",
                (self.scope,),
            ).fetchone()
            traits = row["value"] if row else {"playfulness": 0.5, "warmth": 0.6}
            traits["playfulness"] = round(
                max(0.2, min(0.8, traits["playfulness"] + score * 0.03)), 3
            )
            db.execute(
                "INSERT INTO mao_hybrid.state VALUES(%s,'traits',%s) ON CONFLICT(scope,key) DO UPDATE SET value=excluded.value",
                (self.scope, Jsonb(traits)),
            )
            db.execute(
                "INSERT INTO mao_hybrid.events(scope,kind,data) VALUES(%s,'feedback',%s)",
                (
                    self.scope,
                    Jsonb(
                        {
                            "score": score,
                            "note": str(note)[:500],
                            "source": "direct_user_feedback",
                        }
                    ),
                ),
            )
            return traits

    def request_approval(self, payload, seconds):
        from psycopg.types.json import Jsonb

        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        request_id = hashlib.sha256((self.scope + encoded).encode()).hexdigest()
        with self.connect() as db:
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (request_id,)
            )
            row = db.execute(
                """DELETE FROM mao_hybrid.approvals WHERE id=%s AND scope=%s
                AND approved AND expires>now() RETURNING id""",
                (request_id, self.scope),
            ).fetchone()
            if row:
                return None
            db.execute(
                "DELETE FROM mao_hybrid.approvals WHERE id=%s AND expires<now()",
                (request_id,),
            )
            db.execute(
                """INSERT INTO mao_hybrid.approvals(id,scope,payload,expires) VALUES(%s,%s,%s,now()+%s*interval '1 second')
                ON CONFLICT(id) DO NOTHING""",
                (request_id, self.scope, Jsonb(payload), seconds),
            )
        return {
            "status": "confirmation_required",
            "request_id": request_id,
            "message": "Operator must inspect/approve the exact action with scripts/mao_hybrid.py; retry after approval. Expires, single use.",
        }

    def close(self):
        self.pool.close()
