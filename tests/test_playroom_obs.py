import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from mao_playroom_obs import select_window


class WindowSelectionTests(unittest.TestCase):
    def test_requires_an_exact_unique_operator_selected_title(self):
        selected = {"itemName": "Selected window", "itemValue": "selected:app.exe"}
        other = {"itemName": "Selected window - other", "itemValue": "other:app.exe"}
        self.assertIs(select_window([selected, other], "Selected window"), selected)
        for title in (None, "", " ", "Selected"):
            with self.subTest(title=title), self.assertRaises(ValueError):
                select_window([selected, other], title)
        with self.assertRaises(ValueError):
            select_window([selected, selected], "Selected window")
