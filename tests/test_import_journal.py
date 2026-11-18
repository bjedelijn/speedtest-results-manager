import json
import tempfile
import unittest
from pathlib import Path

from results_manager.import_journal import import_journal
from results_manager.storage import Storage


def event(cursor, unit="iperf3.service"):
    return {
        "__CURSOR": cursor, "__REALTIME_TIMESTAMP": "1795000000000000",
        "MESSAGE": "synthetic measurement log", "_SYSTEMD_UNIT": unit,
        "_BOOT_ID": "synthetic-boot", "_PID": "1234",
    }


class JournalImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "db.sqlite3"
        self.src = Path(self.tmp.name) / "journal.jsonl"

    def write(self, events):
        self.src.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")

    def test_import_and_incremental_replay(self):
        self.write([event("a")])
        result = import_journal(self.db, self.src, "speedtest01", "iperf3")
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["cursor"], "a")
        self.write([event("a"), event("b")])
        result = import_journal(self.db, self.src, "speedtest01", "iperf3")
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["cursor"], "b")
        self.assertEqual(len(Storage(self.db).list_measurements()), 2)

    def test_same_export_noop(self):
        self.write([event("a")])
        import_journal(self.db, self.src, "speedtest01", "iperf3")
        self.assertEqual(import_journal(self.db, self.src, "speedtest01", "iperf3")["inserted"], 0)

    def test_missing_checkpoint_refuses_rewind(self):
        self.write([event("a")])
        import_journal(self.db, self.src, "speedtest01", "iperf3")
        self.write([event("b")])
        with self.assertRaisesRegex(ValueError, "checkpoint cursor absent"):
            import_journal(self.db, self.src, "speedtest01", "iperf3")
        self.assertEqual(Storage(self.db).checkpoint("journal:speedtest01:iperf3"), "a")

    def test_wrong_unit_fails_before_db_creation(self):
        self.write([event("a", "udpst-legacy.service")])
        with self.assertRaisesRegex(ValueError, "unexpected systemd unit"):
            import_journal(self.db, self.src, "speedtest01", "iperf3")
        self.assertFalse(self.db.exists())

    def test_malformed_export_fails_before_db_creation(self):
        self.src.write_text('{"MESSAGE":', encoding="utf-8")
        with self.assertRaises(ValueError):
            import_journal(self.db, self.src, "speedtest01", "iperf3")
        self.assertFalse(self.db.exists())

    def test_legacy_unit(self):
        self.write([event("a", "udpst-legacy.service")])
        result = import_journal(self.db, self.src, "speedtest01", "udpst-legacy")
        self.assertEqual(result["inserted"], 1)

    def test_duplicate_cursor_rejected(self):
        self.write([event("a"), event("a")])
        with self.assertRaisesRegex(ValueError, "duplicate cursors"):
            import_journal(self.db, self.src, "speedtest01", "iperf3")


if __name__ == "__main__":
    unittest.main()
