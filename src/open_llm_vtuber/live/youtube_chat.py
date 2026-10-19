"""Read-only adapter for YouTube's public web chat continuation protocol.

Uses the public web client's current configuration, not a user's API key.
No chat-send, login, moderation or purchase endpoints are implemented.
"""

import asyncio
import json
import re

import httpx


def find_value(value, key):
    if isinstance(value, dict):
        if key in value:
            return value[key]
        values = value.values()
    elif isinstance(value, list):
        values = value
    else:
        return None
    for child in values:
        found = find_value(child, key)
        if found is not None:
            return found
    return None


def page_object(html, name):
    for match in re.finditer(r"(?:var\s+)?" + re.escape(name) + r"\s*=\s*", html):
        try:
            value, _ = json.JSONDecoder().raw_decode(html[match.end() :])
            if isinstance(value, dict):
                return value
        except ValueError:
            pass
    return {}


def live_video_from_page(html):
    player = page_object(html, "ytInitialPlayerResponse")
    live = (
        player.get("microformat", {})
        .get("playerMicroformatRenderer", {})
        .get("liveBroadcastDetails", {})
    )
    ident = player.get("videoDetails", {}).get("videoId", "")
    if (
        live.get("isLiveNow") is True
        and not live.get("endTimestamp")
        and re.fullmatch(r"[\w-]{11}", ident)
    ):
        return ident
    return None


def bootstrap_chat(html):
    cfg = {}
    for match in re.finditer(r"ytcfg\.set\(\s*", html):
        try:
            value, _ = json.JSONDecoder().raw_decode(html[match.end() :])
            if isinstance(value, dict):
                cfg.update(value)
        except ValueError:
            pass
    renderer = find_value(page_object(html, "ytInitialData"), "liveChatRenderer")
    if not isinstance(renderer, dict):
        raise ValueError("YouTube live chat is unavailable or disabled.")
    token = find_value(renderer.get("continuations"), "continuation")
    # Watch-page filter links are navigation tokens, not API continuations.
    # Bootstrap first, then select "Live chat" from the API response's header.
    if (
        not token
        or not cfg.get("INNERTUBE_API_KEY")
        or not isinstance(cfg.get("INNERTUBE_CONTEXT"), dict)
    ):
        raise ValueError(
            "YouTube changed its public chat configuration; cannot connect safely."
        )
    return cfg, token


def rendered_text(value):
    if not isinstance(value, dict):
        return ""
    if isinstance(value.get("simpleText"), str):
        return value["simpleText"]
    return "".join(
        run.get("text", "")
        for run in value.get("runs", [])
        if isinstance(run, dict) and isinstance(run.get("text", ""), str)
    )


def decode_chat(data):
    body = data.get("continuationContents", {}).get("liveChatContinuation", {})
    messages = []
    for action in body.get("actions", []):
        item = action.get("addChatItemAction", {}).get("item", {})
        for kind, message_type in (
            ("liveChatTextMessageRenderer", "text_message"),
            ("liveChatPaidMessageRenderer", "paid_message"),
        ):
            entry = item.get(kind)
            if not isinstance(entry, dict):
                continue
            try:
                stamp = int(entry.get("timestampUsec", 0))
            except (ValueError, TypeError):
                continue
            messages.append(
                dict(
                    message_id=entry.get("id"),
                    timestamp=stamp,
                    action_type="add_chat_item",
                    message_type=message_type,
                    message=rendered_text(entry.get("message")),
                    author={
                        "id": entry.get("authorExternalChannelId"),
                        "name": rendered_text(entry.get("authorName")),
                    },
                )
            )
    continuations = body.get("continuations") or []
    token = find_value(continuations, "continuation")
    delay = find_value(continuations, "timeoutMs")
    delay = max(1, min(15, delay / 1000)) if isinstance(delay, (int, float)) else 3
    return messages, token, delay


async def iter_live_chat(video_id, on_ready=None):
    watch = "https://www.youtube.com/watch?v=" + video_id
    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"},
    ) as client:
        page = await client.get(watch)
        page.raise_for_status()
        if live_video_from_page(page.text) != video_id:
            return  # Scheduled or completed video: never fetch chat replay.
        cfg, token = bootstrap_chat(page.text)
        stream_channel_id = (
            page_object(page.text, "ytInitialPlayerResponse")
            .get("videoDetails", {})
            .get("channelId")
        )
        headers = {
            "Origin": "https://www.youtube.com",
            "Referer": watch,
            "X-Youtube-Client-Name": str(cfg.get("INNERTUBE_CONTEXT_CLIENT_NAME", 1)),
            "X-Youtube-Client-Version": str(cfg.get("INNERTUBE_CLIENT_VERSION", "")),
        }
        visitor = cfg["INNERTUBE_CONTEXT"].get("client", {}).get("visitorData")
        if visitor:
            headers["X-Goog-Visitor-Id"] = visitor
        filter_switches = 0
        while token:
            response = await client.post(
                "https://www.youtube.com/youtubei/v1/live_chat/get_live_chat",
                params={"key": cfg["INNERTUBE_API_KEY"]},
                headers=headers,
                json={"context": cfg["INNERTUBE_CONTEXT"], "continuation": token},
            )
            # Keep request URLs/configuration out of error messages and logs.
            if response.status_code != 200:
                raise ConnectionError(
                    f"YouTube chat returned HTTP {response.status_code}."
                )
            data = response.json()
            body = data.get("continuationContents", {}).get("liveChatContinuation", {})
            menu = find_value(body.get("header"), "subMenuItems") or []
            unfiltered = next(
                (
                    item
                    for item in menu
                    if str(item.get("title", "")).casefold()
                    in ("live chat", "trò chuyện trực tiếp")
                ),
                None,
            )
            if unfiltered and not unfiltered.get("selected"):
                token = find_value(unfiltered.get("continuation"), "continuation")
                filter_switches += 1
                if not token or filter_switches > 2:
                    raise ValueError("Cannot select the full YouTube live chat feed.")
                continue
            if on_ready:
                on_ready()
                on_ready = None
            messages, token, delay = decode_chat(data)
            for message in messages:
                if isinstance(stream_channel_id, str) and re.fullmatch(
                    r"UC[A-Za-z0-9_-]{22}", stream_channel_id
                ):
                    message["stream_channel_id"] = stream_channel_id
                yield message
            if token:
                await asyncio.sleep(delay)
