import unittest
import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from src.open_llm_vtuber.live.game_speech import (
    game_speech_chunks,
    game_speech_prosody,
    PreparedGameSpeech,
)
from src.open_llm_vtuber.live.vua_tieng_viet import VuaTiengViet, WordGameService


class GameSpeechTests(unittest.TestCase):
    def test_result_releases_timeout_and_answer_before_the_explanation(self):
        script = (
            "Hết giờ! Đáp án là mưa rào. Tiếc quá, chưa ai đoán đúng! " + "từ " * 42
        )
        chunks = game_speech_chunks(script)
        self.assertEqual(chunks[:2], ["Hết giờ!", "Đáp án là mưa rào."])
        self.assertEqual(" ".join(chunks), " ".join(script.split()))
        self.assertTrue(all(len(chunk.split()) <= 18 for chunk in chunks))

    def test_clue_number_stays_with_the_hint(self):
        self.assertEqual(
            game_speech_chunks("Gợi ý 2: Cơn mưa đến nhanh rồi tạnh."),
            ["Gợi ý 2: Cơn mưa đến nhanh rồi tạnh."],
        )
        self.assertEqual(game_speech_chunks("   "), [])

    def test_reaction_retains_emotion_without_slowing_the_round(self):
        speech = game_speech_prosody("Tiếc quá, chưa ai đoán đúng!")
        self.assertEqual(speech.mood, "gentle")
        self.assertEqual(speech.tempo, 1.06)
        self.assertLessEqual(speech.pause_ms, 60)


class GameSpeechDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_each_phrase_is_sent_before_synthesizing_the_next(self):
        from src.open_llm_vtuber.conversations.single_conversation import (
            process_single_conversation,
        )

        events = []

        async def speak(**kwargs):
            events.append(kwargs["tts_text"])
            self.assertEqual(kwargs["display_text"].text, kwargs["tts_text"])

        async def flush():
            events.append("sent")

        manager = Mock(
            speak=AsyncMock(side_effect=speak),
            wait_for_completion=AsyncMock(side_effect=flush),
        )
        context = Mock()
        context.character_config.character_name = "Mao"
        context.character_config.avatar = "mao.png"
        module = "src.open_llm_vtuber.conversations.single_conversation"
        script = "Hết giờ! Đáp án là mưa rào. Tiếc quá, chưa ai đoán đúng!"
        with (
            patch(module + ".TTSTaskManager", return_value=manager),
            patch(
                module + ".finalize_conversation_turn", new_callable=AsyncMock
            ) as finalize,
            patch(module + ".cleanup_conversation"),
        ):
            self.assertEqual(
                await process_single_conversation(
                    context, AsyncMock(), "test", "", metadata={"game_speech": script}
                ),
                script,
            )
        self.assertEqual(
            events,
            [
                "Hết giờ!",
                "sent",
                "Đáp án là mưa rào.",
                "sent",
                "Tiếc quá, chưa ai đoán đúng!",
                "sent",
            ],
        )
        context.agent_engine.chat.assert_not_called()
        finalize.assert_awaited_once()

    async def test_prepared_audio_is_reused_without_sharing_deletable_files(self):
        with tempfile.TemporaryDirectory() as folder:

            async def generate(text, file_name_no_ext=None, **kwargs):
                path = Path(folder) / (file_name_no_ext + ".wav")
                path.write_bytes(text.encode())
                return str(path)

            engine = Mock(
                supports_prosody=True,
                async_generate_audio=AsyncMock(side_effect=generate),
                generate_cache_file_name=lambda name: str(
                    Path(folder) / (name + ".wav")
                ),
                remove_file=lambda path: Path(path).unlink(),
            )
            cache = PreparedGameSpeech(engine)
            await cache.prepare("Hết giờ! Đáp án là mưa rào.")
            self.assertEqual(list(Path(folder).iterdir()), [])
            await cache.prepare("Hết giờ!")
            first = await cache.async_generate_audio("Hết giờ!", "one")
            cache.remove_file(first)
            second = await cache.async_generate_audio("Hết giờ!", "two")
            self.assertEqual(Path(second).read_bytes(), "Hết giờ!".encode())
            self.assertEqual(engine.async_generate_audio.await_count, 2)

    async def test_preparation_reserves_tts_then_releases_it_before_start(self):
        gate = asyncio.Event()
        game = VuaTiengViet()
        service = WordGameService(game)
        queue = SimpleNamespace(
            conversation_active=False,
            external_busy=False,
            has_pending_messages=lambda: False,
        )
        service.proxy = SimpleNamespace(message_queue=queue)
        service.speech_cache = SimpleNamespace(
            prepare=AsyncMock(side_effect=lambda script: gate.wait())
        )

        # AsyncMock does not await a coroutine returned by a sync side effect.
        async def prepare(script):
            await gate.wait()

        service.speech_cache.prepare.side_effect = prepare
        game.submit("test", "!vuatiengviet", player_id="test")
        service.prepare_speech_if_idle()
        self.assertTrue(queue.external_busy)
        game.tick(ready=not queue.external_busy)
        self.assertEqual(game.phase, "waiting")
        gate.set()
        await service.prefetch_task
        self.assertFalse(queue.external_busy)
        service.prepare_speech_if_idle()
        self.assertEqual(service.speech_cache.prepare.await_count, 1)
        game.tick(ready=not queue.external_busy)
        self.assertEqual(game.phase, "playing")
        self.assertAlmostEqual(game.deadline - game.started, 60)

    async def test_prefetch_avoids_active_speech_deadlines_and_recovers_errors(self):
        clock = [0]
        game = VuaTiengViet(clock=lambda: clock[0])
        service = WordGameService(game)
        queue = SimpleNamespace(
            conversation_active=True,
            external_busy=False,
            has_pending_messages=lambda: False,
        )
        service.proxy = SimpleNamespace(message_queue=queue)
        service.speech_cache = SimpleNamespace(
            prepare=AsyncMock(side_effect=RuntimeError("unavailable"))
        )
        game.submit("test", "!vuatiengviet", player_id="test")
        service.prepare_speech_if_idle()
        self.assertIsNone(service.prefetch_task)
        queue.conversation_active = False
        service.prepare_speech_if_idle()
        await service.prefetch_task
        self.assertFalse(queue.external_busy)
        game.tick()
        previous = service.prefetch_task
        clock[0] = 19
        service.prepare_speech_if_idle()
        self.assertIs(service.prefetch_task, previous)
        clock[0] = 60
        service.prepare_speech_if_idle()
        game.tick()
        self.assertEqual(game.phase, "finished")

    async def test_future_hints_are_prepared_between_spoken_turns(self):
        clock = [0]
        game = VuaTiengViet(clock=lambda: clock[0])
        service = WordGameService(game)
        queue = SimpleNamespace(
            conversation_active=False,
            external_busy=False,
            has_pending_messages=lambda: False,
        )
        service.proxy = SimpleNamespace(message_queue=queue)
        service.speech_cache = SimpleNamespace(prepare=AsyncMock())
        game.submit("test", "!vuatiengviet", player_id="test")
        service.prepare_speech_if_idle()
        await service.prefetch_task
        game.tick()
        for moment, label in ((10, "Gợi ý 2:"), (30, "Gợi ý 3:")):
            clock[0] = moment
            game.tick()
            service.prepare_speech_if_idle()
            await service.prefetch_task
            self.assertTrue(
                service.speech_cache.prepare.call_args.args[0].startswith(label)
            )
            self.assertFalse(queue.external_busy)

    async def test_due_hint_is_queued_before_future_tts_reservation(self):
        clock = [0]
        game = VuaTiengViet(clock=lambda: clock[0])
        game.submit("test", "!vuatiengviet", player_id="test")
        game.tick()
        game.announcements.clear()
        clock[0] = 20
        pending = []
        queue = SimpleNamespace(
            conversation_active=False,
            external_busy=False,
            has_pending_messages=lambda: bool(pending),
            queue_message=lambda message, **kwargs: pending.append(message),
        )
        service = WordGameService(game)
        service.proxy = SimpleNamespace(
            message_queue=queue,
            clients={"test": True},
            connected=True,
            broadcast_to_clients=AsyncMock(),
        )
        service.speech_cache = SimpleNamespace(prepare=AsyncMock())
        with patch(
            "src.open_llm_vtuber.live.vua_tieng_viet.asyncio.sleep",
            side_effect=asyncio.CancelledError,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await service._run()
        self.assertEqual(pending[0]["game_kind"], "hint-1")
        self.assertIsNone(service.prefetch_task)
        self.assertFalse(queue.external_busy)
