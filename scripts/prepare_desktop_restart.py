"""Release the current local conversation before replacing its audio player."""
import asyncio
import json

import websockets


async def main():
    async with websockets.connect('ws://127.0.0.1:12393/proxy-ws', max_size=10_000_000) as ws:
        async with asyncio.timeout(20):
            while True:
                event = json.loads(await ws.recv())
                if event.get('type') == 'conversation-state':
                    if not event.get('active'):
                        print('Conversation is idle; desktop can restart.')
                        return
                    await ws.send(json.dumps({'type': 'interrupt-signal'}))
                if event.get('type') == 'control' and event.get('text') == 'conversation-chain-end':
                    print('Active conversation released for desktop restart.')
                    return


if __name__ == '__main__':
    asyncio.run(main())
