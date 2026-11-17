import json
import unittest
from results_manager.journal import parse_journal_json


class JournalTests(unittest.TestCase):
    def event(self, **changes):
        obj = {
            "__REALTIME_TIMESTAMP": "1794951524505621",
            "__CURSOR": "s=sample;i=42",
            "_BOOT_ID": "boot-1",
            "MESSAGE": "Accepted connection from 192.0.2.10, port 51234",
        }
        obj.update(changes)
        return json.dumps(obj)

    def test_structured_timestamp_and_cursor(self):
        event = list(parse_journal_json([self.event()]))[0]
        self.assertEqual(event["timestamp_us"], 1794951524505621)
        self.assertTrue(event["timestamp_utc"].endswith("+00:00"))
        self.assertEqual(event["cursor"], "s=sample;i=42")
        self.assertEqual(event["boot_id"], "boot-1")

    def test_blank_lines(self):
        self.assertEqual(list(parse_journal_json(["", "  "])), [])

    def test_rejects_missing_cursor(self):
        with self.assertRaisesRegex(ValueError, "cursor"):
            list(parse_journal_json([self.event(__CURSOR=None)]))

    def test_rejects_missing_timestamp(self):
        with self.assertRaisesRegex(ValueError, "timestamp"):
            list(parse_journal_json([self.event(__REALTIME_TIMESTAMP="not-a-number")]))

    def test_rejects_invalid_json(self):
        with self.assertRaisesRegex(ValueError, "line 1"):
            list(parse_journal_json(["{bad"]))

    def test_rejects_non_string_message(self):
        with self.assertRaisesRegex(ValueError, "MESSAGE"):
            list(parse_journal_json([self.event(MESSAGE=["unexpected"])]))


if __name__ == "__main__":
    unittest.main()
