import json
import tempfile
import unittest
from pathlib import Path
from results_manager.snapshot import read_stable_json, UnstableSnapshotError


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / "stats.json"

    def test_valid_json(self):
        self.file.write_text('{"data_records":[]}', encoding="utf-8")
        self.assertEqual(read_stable_json(self.file), {"data_records": []})

    def test_partial_json_is_rejected(self):
        self.file.write_text('{"data_records":[', encoding="utf-8")
        with self.assertRaises(UnstableSnapshotError):
            read_stable_json(self.file)

    def test_file_size_limit(self):
        self.file.write_bytes(b"x" * 20)
        with self.assertRaisesRegex(ValueError, "size limit"):
            read_stable_json(self.file, max_bytes=10)

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            read_stable_json(self.file, attempts=0)
        with self.assertRaises(ValueError):
            read_stable_json(self.file, max_bytes=0)

    def test_missing_file_is_not_created(self):
        with self.assertRaises(FileNotFoundError):
            read_stable_json(self.file)
        self.assertFalse(self.file.exists())


if __name__ == "__main__":
    unittest.main()
