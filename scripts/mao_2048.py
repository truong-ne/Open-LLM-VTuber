"""Mao plays an external public 2048 website in a dedicated Chrome window.

No game is hosted here. Visible DOM tiles are observations; moves are arrow keys.
"""

import argparse
import asyncio
import json
import sys
import time
from urllib.parse import urlsplit
import uuid

from mao_hybrid import ROOT, config, Store
from src.open_llm_vtuber.agent.hybrid.game2048 import (
    URL,
    KEYS,
    POLICIES,
    GameLedger,
    board_from_tiles,
    choose,
    verified_transition,
)

STATUS = ROOT / "web_tool/mao-5070/state/game2048.json"


def publish(**data):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATUS.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {"game": "2048", "source": URL, "updated_at": time.time(), **data},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    # Windows readers/antivirus can briefly hold the old file without delete
    # sharing. A transient preview failure must never abort the game controller.
    for attempt in range(10):
        try:
            temporary.replace(STATUS)
            return True
        except PermissionError:
            time.sleep(0.025)
    return False


async def observe(page):
    if page.url != URL:
        raise PermissionError("The game left its permitted URL")
    tiles = await page.locator(".tile-container .tile").evaluate_all(
        "els => els.map(e => ({classes:e.className,value:e.querySelector('.tile-inner').textContent}))"
    )
    board = board_from_tiles(tiles)
    score = int(
        await page.locator(".score-container .value").evaluate(
            "e => [...e.childNodes].filter(n => n.nodeType===3).map(n=>n.textContent).join('').trim()"
        )
    )
    return board, score


async def run(args):
    from playwright.async_api import async_playwright

    if (
        not 1 <= args.games <= 8
        or not 20 <= args.moves <= 600
        or not 30 <= args.seconds <= 900
    ):
        raise ValueError("Use 1–8 games, 20–600 moves/game, 30–900 seconds")
    settings = config().model_copy(update={"scope": "mao-game-2048"})
    store = Store(settings)
    ledger = GameLedger(store)
    # Refuse to play without durable storage, rather than pretending to learn.
    champion = ledger.champion()
    results = []
    deadline = time.monotonic() + args.seconds
    profile = ROOT / "private/mao-game-chrome"
    context = None
    try:
        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                str(profile),
                channel="chrome",
                chromium_sandbox=True,
                headless=False,
                viewport={"width": 1440, "height": 720},
                accept_downloads=False,
                permissions=[],
                service_workers="block",
                args=[
                    "--window-size=1456,820",
                    "--window-position=20,20",
                    "--no-first-run",
                    "--disable-session-crashed-bubble",
                ],
            )

            async def guard(route):
                parts = urlsplit(route.request.url)
                if (
                    route.request.method not in {"GET", "HEAD"}
                    or parts.scheme != "https"
                    or parts.hostname != urlsplit(URL).hostname
                ):
                    return await route.abort()
                await route.continue_()

            await context.route("**/*", guard)
            await context.route_web_socket("**/*", lambda ws: ws.close())
            page = context.pages[0] if context.pages else await context.new_page()
            context.on(
                "page",
                lambda popup: asyncio.create_task(popup.close())
                if popup != page
                else None,
            )
            await page.goto(URL, wait_until="networkidle", timeout=30000)
            await page.locator(".tile-container .tile").first.wait_for(timeout=15000)
            for number in range(args.games):
                if time.monotonic() >= deadline:
                    break
                policy = (
                    POLICIES[number % len(POLICIES)]
                    if args.learn
                    else champion["policy"]
                )
                await page.locator(".restart-button").click()
                await asyncio.sleep(0.25)
                before, score = await observe(page)
                run_id = uuid.uuid4().hex
                moves = 0
                outcome = "move_budget"
                valid = True
                publish(
                    phase="playing",
                    policy=policy,
                    score=score,
                    moves=0,
                    run_id=run_id,
                    caption="Đang đọc bàn cờ thật trên Chrome.",
                )
                for _ in range(args.moves):
                    if time.monotonic() >= deadline:
                        outcome = "time_budget"
                        break
                    if await page.locator(".game-message.game-won").count():
                        outcome = "won"
                        break
                    direction = choose(before, policy)
                    if direction is None:
                        outcome = "game_over"
                        break
                    await page.keyboard.press(KEYS[direction])
                    await asyncio.sleep(0.23)
                    after, new_score = await observe(page)
                    if not verified_transition(
                        before, after, direction, score, new_score
                    ):
                        # Animation lag must not become invented progress.
                        await asyncio.sleep(0.25)
                        after, new_score = await observe(page)
                    if not verified_transition(
                        before, after, direction, score, new_score
                    ):
                        valid = False
                        outcome = "unverified_transition"
                        break
                    moves += 1
                    before, score = after, new_score
                    store.event(
                        "game2048_move",
                        {
                            "run_id": run_id,
                            "move": moves,
                            "direction": direction,
                            "score": score,
                            "max_tile": max(before),
                        },
                    )
                    names = {
                        "up": "lên",
                        "down": "xuống",
                        "left": "sang trái",
                        "right": "sang phải",
                    }
                    publish(
                        phase="playing",
                        policy=policy,
                        score=score,
                        moves=moves,
                        run_id=run_id,
                        caption=f"Vừa đi {names[direction]}. Điểm trên game: {score}.",
                    )
                result = {
                    "id": run_id,
                    "policy": policy,
                    "score": score,
                    "moves": moves,
                    "max_tile": max(before),
                    "max_moves": args.moves,
                    "outcome": outcome,
                    "verified": valid,
                }
                champion = ledger.finish(result)
                results.append(result)
                publish(
                    phase="between-games",
                    score=score,
                    moves=moves,
                    policy=policy,
                    caption=f"Ván này đạt {score} điểm, ô lớn nhất {max(before)}. Đã lưu kết quả.",
                )
                if not valid:
                    break
            report = {
                "source": URL,
                "real_website": True,
                "runs": results,
                "strategy": champion,
                "quality_improvement_verified": False,
            }
            if args.learn or args.reflect:
                from review_mao_game import review_games

                report["memory_review"] = await asyncio.to_thread(
                    review_games, args.reflect
                )
            (ROOT / "logs/mao-2048-session.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            publish(
                phase="stopped",
                score=results[-1]["score"] if results else 0,
                caption="Đã hết lượt thử. Kết quả thật đã được lưu; chưa đủ dữ liệu để khẳng định tiến bộ.",
            )
            print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
            # Keep only this owned game window available briefly for scene inspection.
            if args.hold:
                await asyncio.sleep(min(args.hold, 300))
            await context.close()
    finally:
        store.close()
        publish(phase="stopped", caption="Mao đã tạm dừng chơi.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=2)
    parser.add_argument("--moves", type=int, default=250)
    parser.add_argument("--seconds", type=int, default=300)
    parser.add_argument("--learn", action="store_true")
    parser.add_argument(
        "--reflect",
        action="store_true",
        help="Ask local Qwen for an unverified post-game hypothesis",
    )
    parser.add_argument("--hold", type=int, default=0)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
