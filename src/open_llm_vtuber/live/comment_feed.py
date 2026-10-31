"""Bounded, display-only viewer comments; never forwarded to the agent or game."""

from collections import OrderedDict, deque
import re
import time
import uuid


class CommentFeed:
    def __init__(self, *, limit=60, clock=time.time):
        self.session = uuid.uuid4().hex
        self.revision = 0
        self.comments = deque(maxlen=limit)
        self.seen = OrderedDict()
        self.clock = clock

    def add(self, message):
        text = message.get("text")
        if not isinstance(text, str) or not text.strip():
            return False
        source = str(message.get("source") or "desktop")[:100]
        ident = str(message.get("event_id") or "")[:160]
        key = (source, ident)
        if ident and key in self.seen:
            return False
        if ident:
            self.seen[key] = True
            if len(self.seen) > 2000:
                self.seen.popitem(last=False)
        self.revision += 1

        def clean(value, limit):
            return re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", str(value)).strip()[:limit]

        platform = (
            "youtube"
            if source.startswith("youtube")
            else "tiktok"
            if source.startswith(("tiktok", "@"))
            else "desktop"
        )
        self.comments.append(
            {
                "id": self.revision,
                "nickname": clean(message.get("nickname") or "papa", 40),
                "text": clean(text, 300),
                "platform": platform,
                "received_at": self.clock(),
            }
        )
        return True

    def snapshot(self, *, after=0, session=None):
        since = after if session == self.session and 0 <= after <= self.revision else 0
        return {
            "session": self.session,
            "revision": self.revision,
            "comments": [dict(item) for item in self.comments if item["id"] > since],
        }
