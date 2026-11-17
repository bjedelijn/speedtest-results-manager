import sqlite3
import tempfile
import unittest
from pathlib import Path
from results_manager.storage import Storage, content_key


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Storage(Path(self.temp.name) / "results.sqlite3")
        self.db.initialize()

    def test_idempotent_replay(self):
        records = [("udpst_modern", "server:24601:1:2", {"average": {"tx": 1}})]
        first = self.db.ingest_batch("udpst-stats", records, "cursor-1")
        second = self.db.ingest_batch("udpst-stats", records, "cursor-2")
        self.assertEqual(first["inserted"], 1)
        self.assertEqual(second["duplicates"], 1)
        self.assertEqual(self.db.checkpoint("udpst-stats"), "cursor-2")
        self.assertEqual(len(self.db.list_measurements()), 1)

    def test_transaction_rolls_back_checkpoint_and_rows(self):
        self.db.ingest_batch("iperf3", [], "old-cursor")
        with self.assertRaises(ValueError):
            self.db.ingest_batch("iperf3", [
                ("iperf3", "good", {"rate": 250}),
                ("iperf3", "bad", {"rate": float("nan")}),
            ], "new-cursor")
        self.assertEqual(self.db.checkpoint("iperf3"), "old-cursor")
        self.assertEqual(self.db.list_measurements(), [])

    def test_conflicting_source_key_is_error(self):
        self.db.ingest_batch("iperf3", [("iperf3", "same", {"rate": 100})], "first")
        with self.assertRaisesRegex(ValueError, "collision"):
            self.db.ingest_batch("iperf3", [("iperf3", "same", {"rate": 200})], "second")
        self.assertEqual(self.db.checkpoint("iperf3"), "first")
        self.assertEqual(len(self.db.list_measurements()), 1)

    def test_separate_stream_checkpoints(self):
        self.db.ingest_batch("iperf3", [], "cursor-a")
        self.db.ingest_batch("udpst-legacy", [], "cursor-b")
        self.assertEqual(self.db.checkpoint("iperf3"), "cursor-a")
        self.assertEqual(self.db.checkpoint("udpst-legacy"), "cursor-b")

    def test_content_hash_is_order_independent(self):
        self.assertEqual(content_key({"a": 1, "b": 2}), content_key({"b": 2, "a": 1}))

    def test_filter_and_limit(self):
        self.db.ingest_batch("test", [
            ("iperf3", "a", {"rate": 1}),
            ("udpst_modern", "b", {"rate": 2}),
        ], "end")
        self.assertEqual(len(self.db.list_measurements("iperf3")), 1)
        with self.assertRaises(ValueError):
            self.db.list_measurements(limit=0)

    def test_initialize_idempotent(self):
        self.db.initialize()
        self.db.ingest_batch("test", [("iperf3", "a", {})], "cursor")
        self.db.initialize()
        self.assertEqual(len(self.db.list_measurements()), 1)


if __name__ == "__main__":
    unittest.main()
