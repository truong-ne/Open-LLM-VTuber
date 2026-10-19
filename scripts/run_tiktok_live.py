import os
import sys
import asyncio
import argparse
from loguru import logger

# Add project root to path to enable imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from src.open_llm_vtuber.live.tiktok_live import TikTokLivePlatform
from src.open_llm_vtuber.live.idle_host import IdleHost
from src.open_llm_vtuber.config_manager.utils import read_yaml, validate_config


async def main(username: str = "", retry_seconds: float = 15.0):
    """
    Main function to run the TikTok Live platform client.
    Connects to a TikTok live room and forwards comments to the VTuber.
    """
    logger.info("Starting TikTok Live platform client")
    host_task = None

    try:
        # Load configuration
        config_path = os.path.join(project_root, "conf.yaml")
        config_data = read_yaml(config_path)
        config = validate_config(config_data)

        tiktok_config = config.live_config.tiktok_live

        unique_id = username.strip() or tiktok_config.unique_id.strip()
        if not unique_id:
            logger.error(
                "No TikTok username specified. Use --username @your_name or set live_config.tiktok_live.unique_id."
            )
            return

        port = config.system_config.port
        host_task = asyncio.create_task(IdleHost(f"ws://127.0.0.1:{port}/proxy-ws").run())
        while True:
            platform = TikTokLivePlatform(
                unique_id=unique_id,
                batch_size=tiktok_config.batch_size,
                batch_window=tiktok_config.batch_window,
                max_pending_comments=tiktok_config.max_pending_comments,
                min_interval=tiktok_config.min_interval,
                response_timeout=tiktok_config.response_timeout,
                include_nickname=tiktok_config.include_nickname,
                blocked_words=tiktok_config.blocked_words,
                proxy_url=f"ws://127.0.0.1:{port}/proxy-ws",
            )
            await platform.run()
            if retry_seconds <= 0:
                break
            logger.info(
                f"TikTok connection ended or room is offline; retrying in {retry_seconds:g}s"
            )
            await asyncio.sleep(retry_seconds)

    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error(
            "Make sure you have installed TikTokLive with: uv sync --extra tiktok"
        )
    except Exception as e:
        logger.error(f"Error starting TikTok Live client: {e}")
        import traceback

        logger.debug(traceback.format_exc())
    finally:
        if host_task:
            host_task.cancel()
            await asyncio.gather(host_task, return_exceptions=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read TikTok LIVE comments into Mao")
    parser.add_argument("--username", default="", help="Streamer @username")
    parser.add_argument(
        "--retry-seconds", type=float, default=15.0,
        help="Reconnect delay when offline; 0 disables retries",
    )
    args = parser.parse_args()
    try:
        asyncio.run(main(args.username, args.retry_seconds))
    except KeyboardInterrupt:
        logger.info("Shutting down TikTok Live platform")

# Usage: uv run python scripts/run_tiktok_live.py
