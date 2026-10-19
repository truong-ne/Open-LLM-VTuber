"""Bounded, read-only checks of a comment author's public YouTube channel."""

from collections import OrderedDict
from decimal import Decimal, InvalidOperation
import re
import time

import httpx

from .youtube_chat import page_object, find_value, rendered_text

CHANNEL_ID = re.compile(r"UC[A-Za-z0-9_-]{22}")
CREATOR_THRESHOLD = 10_000
# Identity pinned from MixiGaming's own introduction page, not a display name.
MIXIGAMING_CHANNEL = "UCA_23dkEYToAc37hjSsCnXA"


def subscriber_count(text):
    """Parse only English public subscriber labels, never views/video counts.

    YouTube's display is rounded; this value is a public lower-bound estimate.
    Exactly 10K is deliberately insufficient for a strict >10,000 threshold.
    """
    if not isinstance(text, str):
        return None
    match = re.fullmatch(
        r"\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(K|M|B|thousand|million|billion)?\s+subscribers?\s*",
        text,
        re.I,
    )
    if not match:
        return None
    units = {
        "k": 1000,
        "thousand": 1000,
        "m": 1_000_000,
        "million": 1_000_000,
        "b": 1_000_000_000,
        "billion": 1_000_000_000,
    }
    try:
        count = Decimal(match[1].replace(",", "")) * units.get(
            (match[2] or "").lower(), 1
        )
    except InvalidOperation:
        return None
    return int(count) if 0 <= count <= 10_000_000_000 else None


def channel_profile(html, channel_id):
    if not CHANNEL_ID.fullmatch(channel_id):
        return None
    data = page_object(html, "ytInitialData")
    metadata = find_value(data.get("metadata"), "channelMetadataRenderer") or {}
    if metadata.get("externalId") != channel_id:
        return None
    header = data.get("header", {})
    labels = []
    legacy = find_value(header, "subscriberCountText")
    if legacy:
        labels.append(rendered_text(legacy))
    modern = find_value(header, "contentMetadataViewModel") or {}
    for row in modern.get("metadataRows", []):
        for part in row.get("metadataParts", []):
            labels.append(part.get("text", {}).get("content", ""))
    counts = {
        count for label in labels if (count := subscriber_count(label)) is not None
    }
    if len(counts) != 1:
        return None
    count = counts.pop()
    return {
        "channel_id": channel_id,
        "title": str(metadata.get("title", ""))[:100],
        "subscriber_count_lower_bound": count,
        "source_url": f"https://www.youtube.com/channel/{channel_id}",
        "verified_at": time.time(),
        "is_mixi": channel_id == MIXIGAMING_CHANNEL,
    }


class YouTubeCreatorLookup:
    def __init__(self, *, clock=time.monotonic):
        self.clock, self.cache = clock, OrderedDict()

    async def lookup(self, channel_id):
        if not isinstance(channel_id, str) or not CHANNEL_ID.fullmatch(channel_id):
            return None
        cached = self.cache.get(channel_id)
        if cached and self.clock() < cached[0]:
            self.cache.move_to_end(channel_id)
            return cached[1]
        profile = None
        try:
            async with httpx.AsyncClient(
                timeout=5,
                follow_redirects=False,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            ) as client:
                response = await client.get(
                    f"https://www.youtube.com/channel/{channel_id}", params={"hl": "en"}
                )
                if response.status_code == 200:
                    profile = channel_profile(response.text, channel_id)
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            pass  # Missing/changed/hidden metadata is unknown, never famous.
        self.cache[channel_id] = (self.clock() + (3600 if profile else 600), profile)
        self.cache.move_to_end(channel_id)
        while len(self.cache) > 512:
            self.cache.popitem(last=False)
        return profile
