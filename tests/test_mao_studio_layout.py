"""Mao livestream captions remain visible without legacy operator panels."""

import json
from pathlib import Path
import subprocess
import unittest

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class StudioLayoutTests(unittest.TestCase):
    def test_livestream_hides_composer_and_keeps_captions_visible(self):
        subprocess.run(
            ["node", "tests/test_mao_studio_ui.mjs", "--layout-fixture"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        markup = (ROOT / "logs/mao-studio-layout-fixture.html").read_text(
            encoding="utf-8"
        )
        theme = (ROOT / "web_tool/mao-5070/draco/desktop-theme.css").read_text(
            encoding="utf-8"
        )
        reports = []
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(
                channel="chrome", headless=True, args=["--disable-gpu"]
            )
            page = browser.new_page()
            try:
                for width, height, expanded, collapsed in [
                    (900, 700, False, False),
                    (1920, 1080, False, False),
                    (2560, 1440, False, False),
                    (560, 700, False, False),
                    (360, 740, False, False),
                ]:
                    with self.subTest(
                        width=width, expanded=expanded, collapsed=collapsed
                    ):
                        page.set_viewport_size({"width": width, "height": height})
                        sidebar = 0
                        page.set_content(
                            f'<html><head><meta charset="UTF-8"><style>body{{margin:0}}main{{position:absolute;top:30px;bottom:0;left:{sidebar}px;right:0;overflow:hidden}}{theme}</style></head><body data-mode="window">{markup}</body></html>'
                        )
                        page.locator(".mao-caption p").evaluate(
                            "(e)=>e.textContent='Có vẻ như mọi người thường nghĩ rằng \"bình yên\" là trạng thái của sự tĩnh lặng hoặc thiếu hoạt động. Nhưng với tôi, khoảnh khắc im lặng cũng là nơi chứa đựng vô vàn ý tưởng, cảm xúc và những điều thú vị đang chờ được khám phá. Hôm nay bạn có muốn cùng Mao chia sẻ một câu chuyện không?'"
                        )
                        page.screenshot(
                            path=str(
                                ROOT
                                / f"logs/mao-studio-layout-{width}-{int(expanded)}-{int(collapsed)}.png"
                            )
                        )
                        self.assertFalse(
                            page.locator("#mao-window-footer").is_visible()
                        )
                        self.assertEqual(
                            page.locator(".mao-composer,.mao-studio-header").count(), 0
                        )
                        overflow = page.locator(".mao-caption").evaluate(
                            "(e)=>({client:e.clientHeight,scroll:e.scrollHeight})"
                        )
                        self.assertLessEqual(
                            overflow["scroll"],
                            overflow["client"] + 1,
                            "Dialogue text must fit without scrolling or clipping",
                        )
                        paragraph = page.locator(".mao-caption p").bounding_box()
                        self.assertGreaterEqual(paragraph["y"], 30)
                        self.assertLessEqual(
                            paragraph["y"] + paragraph["height"], height - 20
                        )
                        caption = page.locator("#mao-window-subtitle").bounding_box()
                        self.assertGreater(caption["y"], 30)
                        self.assertGreaterEqual(caption["x"], sidebar)
                        self.assertLessEqual(caption["y"] + caption["height"], height)
                        self.assertLessEqual(caption["x"] + caption["width"], width)
                        reports.append(
                            {
                                "width": width,
                                "height": height,
                                "sidebar": expanded,
                                "caption": caption,
                            }
                        )
            finally:
                browser.close()
        (ROOT / "logs/mao-studio-layout.json").write_text(
            json.dumps({"status": "passed", "cases": reports}, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
