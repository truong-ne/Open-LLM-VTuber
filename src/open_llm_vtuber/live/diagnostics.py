"""Local operator view of live reception, queue and confirmed delivery."""

import time
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException, Request

from .comment_state import CommentState, COMMENT_STATE_PATH
from .idle_host_storage import read_json
from .viewer_memory import ViewerMemory

ROOT = Path(__file__).resolve().parents[3]


def live_snapshot(root=ROOT, state_path=COMMENT_STATE_PATH, audit=None, memory=None):
    now = time.time()
    reader = read_json(root / "private/tiktok-reader-health.json")
    queue = read_json(root / "private/mao-chat-activity.json")
    host = read_json(root / "private/mao-host-status.json")
    desktop = read_json(root / "private/draco-desktop-status.json")
    fresh = 0 <= now - reader.get("updated_at", 0) < 75
    connection = (
        "offline"
        if reader.get("phase") == "offline"
        else "stale"
        if not fresh
        else "connected"
        if reader.get("connected")
        else "reconnecting"
    )
    comments = (audit or CommentState(state_path)).snapshot(
        account=reader.get("account")
    )
    if now - queue.get("updated_at", 0) < 10:
        queue["next_comments"] = [
            {"nickname": row["nickname"], "text": row["text"]}
            for row in reversed(comments)
            if row["state"] == "queued" and not row["batch_id"]
        ][:5]
    return {
        "server_now": now,
        "connection": connection,
        "reader": reader,
        "queue": queue if now - queue.get("updated_at", 0) < 10 else {},
        "host": host if now - host.get("updated_at", 0) < 10 else {},
        "desktop": {
            key: desktop.get(key)
            for key in (
                "socket",
                "audioStarted",
                "audioEnded",
                "audioErrors",
                "updatedAt",
            )
        },
        "comments": comments,
        "memory": (
            memory
            or ViewerMemory(Path(state_path).with_name("mao-viewer-memory.sqlite3"))
        ).summary(
            "tiktok-live:" + reader["account"].casefold()
            if reader.get("account")
            else None
        ),
        "note": "Chỉ truy vết được bình luận đã tới bộ đọc; trạng thái kết nối không chứng minh nhận đủ bình luận TikTok.",
    }


def install_live_diagnostics(app, *, root=ROOT, state_path=COMMENT_STATE_PATH):
    audit = CommentState(state_path)
    memory = ViewerMemory(Path(state_path).with_name("mao-viewer-memory.sqlite3"))

    @app.get("/api/live/diagnostics")
    def diagnostics(request: Request):
        if request.client and request.client.host not in (
            "127.0.0.1",
            "::1",
            "localhost",
            "testclient",
        ):
            raise HTTPException(403)
        origin = request.headers.get("origin")
        if origin and origin != "null":
            parsed = urlparse(origin)
            if (
                parsed.hostname not in ("127.0.0.1", "localhost")
                or parsed.port != request.url.port
            ):
                raise HTTPException(403)
        return live_snapshot(root, state_path, audit, memory)
