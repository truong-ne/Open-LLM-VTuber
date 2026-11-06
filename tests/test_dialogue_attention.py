import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from src.open_llm_vtuber.dialogue.attention import continues_topic, quiet_request
from src.open_llm_vtuber.dialogue.focus import Focus
from src.open_llm_vtuber.dialogue.intent import response_plan
import test_runtime_architecture as architecture


class QuietAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_quiet_blocks_queued_proposals_but_allows_direct_input(self):
        from src.open_llm_vtuber.interaction.service import TurnSession

        for metadata in ({"proactive_speak": True}, {"narration_speech": "hello"}, {}):
            turn = TurnSession.__new__(TurnSession)
            turn.admitted = turn.accepted = turn.persist = True
            turn.metadata = metadata
            turn.room, turn.actor = "room", "person-a"
            turn.event = SimpleNamespace(visibility="private")
            turn.journal = SimpleNamespace(start=Mock(return_value=True))
            turn.development = SimpleNamespace(
                effective=Mock(return_value={"settings": {}})
            )
            turn.focus = SimpleNamespace(
                room_waiting=Mock(return_value=False),
                room_quiet=Mock(return_value=True),
            )
            turn.finish = AsyncMock()
            turn.delivery = SimpleNamespace(modality="text")
            turn.context = SimpleNamespace()
            accepted = await turn.begin()
            if metadata:
                self.assertFalse(accepted)
                turn.finish.assert_awaited_once_with("rejected")
                self.assertEqual(turn.rejection, "declined_policy")
            else:
                self.assertTrue(accepted)
                turn.focus.room_quiet.assert_not_called()
                turn.finish.assert_not_called()


class AttentionParsingTests(unittest.TestCase):
    def test_old_schema_remains_usable_without_new_columns(self):
        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        store = Mock(scope="test-legacy")
        store.connect.return_value.__enter__ = Mock(return_value=db)
        store.connect.return_value.__exit__ = Mock(return_value=False)
        focus = Focus(store)
        source = {
            "room_id": "room",
            "actor_id": "person",
            "visibility": "private",
            "synthetic": False,
            "kind": "input",
            "raw_expired": False,
        }
        with patch.object(focus, "source", return_value=source):
            focus.input("event", "Papa muốn yên tĩnh")
            self.assertIsNone(focus.current("room", "person", "private"))
            self.assertFalse(focus.room_quiet("room", "private"))
        for call in db.execute.call_args_list:
            self.assertNotIn("topic_event", call.args[0])
            self.assertNotIn("quiet_until", call.args[0])

    def test_explicit_quiet_and_resume(self):
        for text in (
            "Papa muốn yên tĩnh.",
            "Mao im lặng một chút nhé",
            "Đừng tự mở chuyện nữa",
        ):
            self.assertEqual(quiet_request(text), "quiet")
            self.assertEqual(response_plan(text).mode, "quiet")
        for text in ("Mao nói tiếp đi", "Cứ chủ động nói chuyện lại nhé"):
            self.assertEqual(quiet_request(text), "resume")
            self.assertEqual(response_plan(text).mode, "resume")

    def test_no_inference_from_negation_quotes_reports_or_silence(self):
        for text in (
            "",
            "Ừ",
            "Papa không muốn yên tĩnh",
            "Đừng im lặng nhé",
            "Dịch câu “Mao im lặng một chút nhé”",
            "Trong truyện nhân vật muốn yên tĩnh",
            "```Mao nói tiếp đi```",
        ):
            self.assertIsNone(quiet_request(text), text)

    def test_continuations_do_not_swallow_new_topics(self):
        for text in ("Ừ", "Vẫn vậy.", "Mao hiểu sai rồi"):
            self.assertTrue(continues_topic(text))
        for text in ("Đổi chủ đề nhé", "Tính 2+3", "Vẫn vậy, nhưng giờ nói về mèo nhé"):
            self.assertFalse(continues_topic(text))


@unittest.skipUnless(
    os.environ.get("MAO_TEST_POSTGRES") == "1", "PostgreSQL integration opt-in"
)
class AttentionDatabaseTests(unittest.TestCase):
    setUp = architecture.ArchitectureDatabaseTests.setUp
    tearDown = architecture.ArchitectureDatabaseTests.tearDown
    event = architecture.ArchitectureDatabaseTests.event

    def test_live_question_pause_expires_without_expiring_topic_or_private_pause(self):
        focus = Focus(self.store)
        for visibility in ("public", "private"):
            event, _ = self.event("Chuyện món ăn", room=visibility, visibility=visibility)
            focus.input(event.event_id, event.content)
            focus.delivered(event.event_id, "Bạn chọn món nào?")
            self.assertTrue(focus.room_waiting(visibility))
            with self.store.connect() as db:
                db.execute(
                    "UPDATE mao_hybrid.dialogue_focus SET expires=now()+interval '9 minutes' WHERE scope=%s AND room_id=%s",
                    (self.store.scope, visibility),
                )
            self.assertEqual(focus.room_waiting(visibility), visibility == "private")
            self.assertIsNotNone(focus.current(visibility, "person-a", visibility))

    def test_later_control_in_same_input_updates_database_consistently(self):
        focus = Focus(self.store)
        quiet, _ = self.event("Papa muốn yên tĩnh")
        focus.input(quiet.event_id, quiet.content)
        self.assertTrue(focus.room_quiet("room", "private"))
        resumed, _ = self.event("Papa muốn yên tĩnh. Bây giờ Mao nói tiếp đi.")
        focus.input(resumed.event_id, resumed.content)
        self.assertFalse(focus.room_quiet("room", "private"))
        self.assertEqual(quiet_request(resumed.content), "resume")

    def test_topic_retains_its_source_across_short_follow_up_and_forgetting(self):
        focus = Focus(self.store)
        original, _ = self.event("Papa kể về buổi đi chơi hôm nay")
        focus.input(original.event_id, original.content)
        short, _ = self.event("Ừ")
        focus.input(short.event_id, short.content)
        current = focus.current("room", "person-a", "private")
        self.assertEqual(current["topic"], original.content)
        self.assertEqual(current["topic_event"], original.event_id)
        self.assertEqual(current["source_event"], short.event_id)
        focus.delivered(short.event_id, "Papa muốn kể đoạn tiếp theo không?")
        self.assertTrue(focus.room_waiting("room"))
        self.repo.forget_source(original.event_id)
        self.assertIsNone(focus.current("room", "person-a", "private"))

    def test_new_topic_or_expiry_does_not_keep_old_topic(self):
        focus = Focus(self.store)
        old, _ = self.event("Chuyện hôm nay")
        focus.input(old.event_id, old.content)
        new, _ = self.event("Đổi chủ đề, nói về mèo nhé")
        focus.input(new.event_id, new.content)
        self.assertEqual(
            focus.current("room", "person-a", "private")["topic"], new.content
        )
        with self.store.connect() as db:
            db.execute(
                "UPDATE mao_hybrid.dialogue_focus SET expires=now()-interval '1 second' WHERE scope=%s",
                (self.store.scope,),
            )
        short, _ = self.event("Vẫn vậy")
        focus.input(short.event_id, short.content)
        self.assertEqual(
            focus.current("room", "person-a", "private")["topic"], short.content
        )

    def test_quiet_is_scoped_and_resume_requires_same_actor(self):
        focus = Focus(self.store)
        quiet, _ = self.event("Papa muốn yên tĩnh")
        focus.input(quiet.event_id, quiet.content)
        self.assertTrue(focus.room_quiet("room", "private"))
        self.assertFalse(focus.room_quiet("another-room", "private"))
        self.assertFalse(focus.room_quiet("room", "public"))
        self.assertFalse(focus.room_quiet("room", "test"))
        other, _ = self.event("Mao nói tiếp đi", actor="person-b")
        focus.input(other.event_id, other.content)
        self.assertTrue(focus.room_quiet("room", "private"))
        direct, _ = self.event("Tính 2+3")
        focus.input(direct.event_id, direct.content)
        self.assertTrue(focus.room_quiet("room", "private"))
        resume, _ = self.event("Mao nói tiếp đi")
        focus.input(resume.event_id, resume.content)
        self.assertFalse(focus.room_quiet("room", "private"))

    def test_quiet_expires_and_forgetting_original_source_clears_it(self):
        focus = Focus(self.store)
        quiet, _ = self.event("Papa muốn yên tĩnh")
        focus.input(quiet.event_id, quiet.content)
        later, _ = self.event("Ừ")
        focus.input(later.event_id, later.content)
        with self.store.connect() as db:
            db.execute(
                "UPDATE mao_hybrid.dialogue_focus SET quiet_until=now()-interval '1 second' WHERE scope=%s",
                (self.store.scope,),
            )
        self.assertFalse(focus.room_quiet("room", "private"))
        focus.input(quiet.event_id, quiet.content)
        focus.input(later.event_id, later.content)
        self.repo.forget_source(quiet.event_id)
        self.assertFalse(focus.room_quiet("room", "private"))

    def test_public_or_host_input_cannot_mute_private_output(self):
        focus = Focus(self.store)
        public, _ = self.event("Papa muốn yên tĩnh", visibility="public")
        focus.input(public.event_id, public.content)
        self.assertFalse(focus.room_quiet("room", "private"))
        host, _ = self.event("Papa muốn yên tĩnh")
        with self.store.connect() as db:
            db.execute(
                "UPDATE mao_hybrid.interaction_events SET kind='host_proposal' WHERE scope=%s AND id=%s",
                (self.store.scope, host.event_id),
            )
        focus.input(host.event_id, host.content)
        self.assertFalse(focus.room_quiet("room", "private"))
