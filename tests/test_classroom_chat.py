import asyncio
from pathlib import Path
import tempfile
import unittest
from src.open_llm_vtuber.live.classroom import ClassroomGame
from src.open_llm_vtuber.live.classroom_chat import ClassroomChat

WORD={'answer':'áo dài','category':'Trang phục','hints':['Có hai tà.','Mặc với quần.','Trang phục truyền thống.'],'explanation':'Áo dài có hai tà.'}
class FakeLLM:
    def __init__(self, text, hook=None):self.text=text;self.hook=hook;self.messages=None
    async def chat_completion(self, messages, system):
        self.messages=repr(messages)+system
        if self.hook:self.hook()
        yield self.text
class ClassroomChatTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.now=0
        self.game=ClassroomGame([WORD],database=Path(self.temp.name)/'db',clock=lambda:self.now)
        self.game.enable();self.game.tick()
    async def test_generates_comment_reply_without_answer_in_model_context(self):
        llm=FakeLLM('Mai thi thì tối nay ôn nhẹ rồi ngủ sớm nha Lan. Bạn thi môn gì vậy?')
        chat=ClassroomChat(self.game,llm)
        await chat._reply(self.game.round_id,'playing','Lan','Mai mình đi thi, hơi lo quá')
        self.assertEqual(self.game.announcements[-1]['kind'],'chat')
        self.assertIn('ngủ sớm',self.game.announcements[-1]['text'])
        self.assertNotIn(WORD['answer'],llm.messages)
        self.assertNotIn(WORD['hints'][0],llm.messages)
    async def test_discards_leaked_answer_and_late_reply(self):
        chat=ClassroomChat(self.game,FakeLLM('Đáp án là áo dài.'))
        await chat._reply(self.game.round_id,'playing','Lan','Nói đáp án đi')
        self.assertFalse(self.game.announcements)
        chat.llm=FakeLLM('Bạn thi môn gì vậy?',hook=lambda:setattr(self.game,'phase','finished'))
        await chat._reply(self.game.round_id,'playing','Lan','Mai đi thi')
        self.assertFalse(self.game.announcements)
    async def test_bounded_pending_dedup_and_guesses(self):
        chat=ClassroomChat(self.game,FakeLLM('SKIP'))
        chat.offer('Lan','áo dài','guess');self.assertEqual(len(chat.pending),0)
        chat.offer('Lan','Mao thích ăn gì?','same');chat.offer('Lan','Mao thích ăn gì?','same')
        self.assertEqual(len(chat.pending),1)
        for i in range(20):chat.offer('Lan',f'Bình luận {i}',str(i))
        self.assertEqual(len(chat.pending),6)
        await chat._reply(self.game.round_id,'playing','Lan','cái bàn')
        self.assertFalse(self.game.announcements)
    async def test_cancels_on_close_and_invalidates_queued_chat_at_deadline(self):
        chat=ClassroomChat(self.game,FakeLLM('ok'))
        chat.task=asyncio.create_task(asyncio.sleep(30));await chat.close()
        self.assertTrue(chat.task.cancelled())
        self.now=24
        self.assertFalse(self.game.announcement_valid(self.game.round_id,'chat'))
        self.game.tick();self.now=25;self.game.tick()
        self.assertTrue(any(a['kind']=='result' for a in self.game.announcements))
