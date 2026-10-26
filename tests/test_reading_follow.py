import unittest
from pathlib import Path

from scripts.mao_reading_follow import ReadingFollower


class ReadingFollowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        chrome=Path('C:/Program Files/Google/Chrome/Application/chrome.exe')
        if not chrome.exists():self.skipTest('Local Chrome is unavailable')
        from playwright.async_api import async_playwright
        self.runtime=await async_playwright().start()
        self.browser=await self.runtime.chromium.launch(executable_path=str(chrome),headless=True)
        self.page=await self.browser.new_page(viewport={'width':900,'height':600})
        await self.page.set_content('''<html><head></head><body><h1>Article</h1>
            <div style="height:1100px"></div>
            <p id="first">Active listening helps people feel heard and understood before advice is offered.</p>
            <div style="height:900px"></div>
            <p id="second">Different emotions deserve different responses; gentle curiosity leaves space for clarification.</p>
            <div style="height:1000px"></div></body></html>''')
        self.follower=ReadingFollower()

    async def asyncTearDown(self):
        if hasattr(self,'browser'):
            await self.browser.close()
            await self.runtime.stop()

    async def test_reading_scrolls_to_source_paragraph_and_follows_next_explanation(self):
        self.assertTrue(await self.follower.focus(self.page,'Active listening helps people feel heard and understood before advice is offered.'))
        await self.page.wait_for_function("Math.abs(document.querySelector('#first').getBoundingClientRect().top-300)<80")
        self.assertGreater(await self.page.evaluate('scrollY'),500)
        self.assertEqual(await self.page.locator('[data-mao-reading-active]').get_attribute('id'),'first')
        self.assertTrue(await self.follower.focus(self.page,'Different emotions deserve different responses; gentle curiosity leaves space for clarification.'))
        await self.page.wait_for_function("Math.abs(document.querySelector('#second').getBoundingClientRect().top-300)<80")
        self.assertEqual(await self.page.locator('[data-mao-reading-active]').count(),1)
        self.assertEqual(await self.page.locator('[data-mao-reading-active]').get_attribute('id'),'second')
        await self.follower.clear(self.page)
        self.assertEqual(await self.page.locator('[data-mao-reading-active]').count(),0)

    async def test_missing_paragraph_does_not_scroll_to_an_unrelated_position(self):
        self.assertFalse(await self.follower.focus(self.page,'This source sentence is not present anywhere in the visible article.'))
        self.assertEqual(await self.page.evaluate('scrollY'),0)
        self.assertFalse(self.follower.current['matched'])

    async def test_source_spacing_around_inline_heading_does_not_break_following(self):
        await self.page.set_content('<body><div style="height:1200px"></div><p><b>Brainstorm.</b> Come up with words that match your emotional response.</p><div style="height:1000px"></div></body>')
        self.assertTrue(await self.follower.focus(self.page,'Brainstorm . Come up with words that match your emotional response.'))
