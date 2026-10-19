"""Read the configured YouTube stream into Mao's existing speech queue."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.open_llm_vtuber.config_manager.utils import read_yaml, validate_config
from src.open_llm_vtuber.live.youtube_live import YouTubeLivePlatform
from scripts.run_local_host import DesktopHost


async def main(args):
    config = validate_config(read_yaml(ROOT / "conf.yaml"))
    settings = config.live_config.youtube_live
    reader = YouTubeLivePlatform(
        channel=args.channel or settings.channel,
        video_url=args.video or settings.video_url,
        poll_interval=settings.poll_interval,
        batch_size=settings.batch_size,
        max_pending_comments=settings.max_pending_comments,
        batch_window=settings.batch_window,
        min_interval=settings.min_interval,
        response_timeout=settings.response_timeout,
        include_nickname=settings.include_nickname,
        blocked_words=settings.blocked_words,
        proxy_url=f"ws://127.0.0.1:{config.system_config.port}/proxy-ws",
    )
    if args.check:
        video = await reader.resolve_live()
        reader.video_id = video
        reader.report("live-detected" if video else "waiting-for-live")
        print(
            json.dumps(
                {
                    "channel": reader.channel_url,
                    "live_video_id": video,
                    "phase": "live-detected" if video else "waiting-for-live",
                }
            )
        )
        return
    host = asyncio.create_task(DesktopHost(reader._proxy_url).run())
    try:
        await reader.run()
    finally:
        host.cancel()
        await asyncio.gather(host, return_exceptions=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Read public YouTube LIVE chat for Mao"
    )
    parser.add_argument("--channel", default="")
    parser.add_argument("--video", default="")
    parser.add_argument("--check", action="store_true")
    try:
        asyncio.run(main(parser.parse_args()))
    except KeyboardInterrupt:
        pass
