import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from mao_memories import get_memory, list_memories, parse_query


class MemoryBrowserTests(unittest.TestCase):
    def store(self):
        store = MagicMock()
        store.scope = "mao-private-scope"
        return store, store.connect.return_value.__enter__.return_value

    def test_query_rejects_unbounded_and_scope_override_parameters(self):
        for params in (
            {"scope": ["other-user"]}, {"q": ["x" * 201]},
            {"kind": ["unknown"]}, {"state": ["unknown"]},
            {"page": ["0"]}, {"page": ["10001"]},
            {"page": ["1; SELECT 1"]}, {"q": ["one", "two"]},
        ):
            with self.subTest(params=params), self.assertRaises(ValueError):
                parse_query(params)
        self.assertEqual(parse_query({})["state"], "active")

    def test_list_is_read_only_scope_bound_and_search_uses_literal_parameters(self):
        store, db = self.store()
        db.execute.side_effect = [
            Mock(), Mock(fetchone=lambda: {"total": 3, "active": 2, "expired": 1}),
            Mock(fetchone=lambda: {"total": 1}),
            Mock(fetchall=lambda: [{"id": 42, "kind": "social", "content": "Example"}]),
        ]
        result = list_memories(query="Trà 100%_!", kind="social", page=99, store=store)
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["items"][0]["id"], "42")
        calls = db.execute.call_args_list
        self.assertIn("READ ONLY", calls[0].args[0])
        for call in calls[1:]:
            self.assertIn("scope=%s", call.args[0])
            self.assertEqual(call.args[1][0], store.scope)
        self.assertIn("expires>now()", calls[-1].args[0])
        self.assertIn("kind=%s", calls[-1].args[0])
        self.assertNotIn("Trà", calls[-1].args[0])
        self.assertEqual(calls[-1].args[1][2], "%tra 100!%!_!!%")
        self.assertEqual(calls[-1].args[1][-2:], [20, 0])

    def test_expired_filter_and_empty_results_have_a_valid_first_page(self):
        store, db = self.store()
        db.execute.side_effect = [
            Mock(), Mock(fetchone=lambda: {"total": 0, "active": 0, "expired": 0}),
            Mock(fetchone=lambda: {"total": 0}), Mock(fetchall=lambda: []),
        ]
        result = list_memories(state="expired", store=store)
        self.assertEqual((result["page"], result["pages"], result["items"]), (1, 1, []))
        self.assertIn("expires<=now()", db.execute.call_args.args[0])

    def test_detail_cannot_read_a_different_scope_and_rejects_bad_ids(self):
        store, db = self.store()
        db.execute.return_value.fetchone.return_value = None
        self.assertIsNone(get_memory("42", store=store))
        self.assertEqual(db.execute.call_args.args[1], (store.scope, 42))
        self.assertIn("scope=%s AND id=%s", db.execute.call_args.args[0])
        self.assertNotRegex(db.execute.call_args.args[0], r"(?:SELECT |,)embedding\s*(?:,|FROM)")
        for ident in ("0", "-1", "abc", "42/extra", "1 OR 1=1", str(2**63)):
            with self.subTest(ident=ident), self.assertRaises(ValueError):
                get_memory(ident, store=store)

    def test_owned_store_is_closed_after_database_failure(self):
        store, db = self.store()
        db.execute.side_effect = RuntimeError("Database unavailable")
        with patch("mao_memories.profile_store", return_value=store):
            with self.assertRaises(RuntimeError):
                list_memories()
        store.close.assert_called_once()
