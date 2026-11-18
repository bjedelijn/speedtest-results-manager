import json
import tempfile
import unittest
from pathlib import Path

from results_manager.storage import Storage
from results_manager.sync import sync_existing


def event(cursor, message):
    return {"__CURSOR": cursor, "__REALTIME_TIMESTAMP": "1795000000000000",
            "MESSAGE": message, "_SYSTEMD_UNIT": "iperf3.service",
            "_BOOT_ID": "synthetic-boot", "_PID": "42"}


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "db.sqlite3"
        self.journal = Path(self.tmp.name) / "iperf.jsonl"
        self.stats = Path(self.tmp.name) / "stats.json"

    def write_journal(self):
        entries = [
            event("a", "Accepted connection from 192.0.2.5, port 40001"),
            event("b", "[  5]   0.00-10.00 sec  100 MBytes  83.9 Mbits/sec  receiver"),
        ]
        self.journal.write_text("".join(json.dumps(x) + "\n" for x in entries), encoding="utf-8")

    def write_stats(self):
        self.stats.write_text(json.dumps({
            "start_timestamp": 1795000000.0, "control_port": 24601,
            "software_version": "9.1.0", "protocol_version": 20,
            "data_records": [{
                "start_datetime": "2026-11-18T12:00:00Z",
                "end_datetime": "2026-11-18T12:00:10Z",
                "maximum": {}, "average": {},
            }],
        }), encoding="utf-8")

    def test_combined_sync_and_replay(self):
        self.write_journal()
        self.write_stats()
        first = sync_existing(self.db, "speedtest01",
                              iperf3=self.journal, modern=self.stats)
        self.assertEqual(first["iperf3_results"]["inserted"], 1)
        self.assertEqual(first["udpst_modern_stats"]["inserted"], 1)
        again = sync_existing(self.db, "speedtest01",
                              iperf3=self.journal, modern=self.stats)
        self.assertEqual(again["iperf3_results"]["inserted"], 0)
        self.assertEqual(again["udpst_modern_stats"]["inserted"], 0)
        self.assertEqual(len(Storage(self.db).list_measurements()), 4)

    def test_no_source_refused(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            sync_existing(self.db, "speedtest01")
        self.assertFalse(self.db.exists())

    def test_invalid_server_id_refused(self):
        with self.assertRaisesRegex(ValueError, "invalid server_id"):
            sync_existing(self.db, "server:bad", modern=self.stats)

    def test_failed_import_does_not_create_db(self):
        self.stats.write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError):
            sync_existing(self.db, "speedtest01", modern=self.stats)
        self.assertFalse(self.db.exists())


if __name__ == "__main__":
    unittest.main()
