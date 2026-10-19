"""Run local conversation hosting without connecting to a TikTok room."""
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.open_llm_vtuber.live.idle_host import IdleHost


class DesktopHost(IdleHost):
    def ready(self, now):
        try:
            status = json.loads((ROOT / 'private/draco-desktop-status.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return False
        return bool(
            status.get('ready')
            and status.get('visible')
            and status.get('socket') == 'open'
            and not status.get('lastError')
            and time.time() * 1000 - status.get('updatedAt', 0) < 10000
            and super().ready(now)
        )


if __name__ == '__main__':
    asyncio.run(DesktopHost(
        'ws://127.0.0.1:12393/proxy-ws',
        activity_path=ROOT / 'private/mao-local-chat-activity.json',
    ).run())
