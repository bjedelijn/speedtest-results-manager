import json
import tempfile
import unittest
from pathlib import Path

from results_manager.import_stats import import_file, make_records
from results_manager.storage import Storage


def sample():
    return {
        "start_timestamp": 1794951524.505621,
        "control_port": 24601,
        "software_version": "9.1.0",
        "protocol_version": 20,
        "schema_version": 1.0,
        "data_records": [
            {
                "start_datetime": "2026-11-17T22:38:44+01:00",
                "end_datetime": "2026-11-17T22:38:54+01:00",
                "maximum": {"allocated": {"connection_count": 2}},
                "average": {"delivered": {"tx_ip_rate_mbps": 123.5}},
            }
        ],
    }


class StatsImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "results.sqlite3"
        self.src = Path(self.tmp.name) / "stats.json"

    def write(self, value):
        self.src.write_text(json.dumps(value), encoding="utf-8")

    def test_import_and_replay(self):
        self.write(sample())
        self.assertEqual(import_file(self.db, self.src, "speedtest01")["inserted"], 1)
        self.assertEqual(import_file(self.db, self.src, "speedtest01")["duplicates"], 1)
        records = Storage(self.db).list_measurements()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["payload"]["kind"], "server_statistics")

    def test_appended_interval(self):
        data = sample()
        self.write(data)
        import_file(self.db, self.src, "speedtest01")
        data["data_records"].append({
            "start_datetime": "2026-11-17T22:38:54+01:00",
            "end_datetime": "2026-11-17T22:39:04+01:00",
            "average": {"delivered": {"tx_ip_rate_mbps": 200}},
        })
        self.write(data)
        outcome = import_file(self.db, self.src, "speedtest01")
        self.assertEqual(outcome["inserted"], 1)
        self.assertEqual(outcome["duplicates"], 1)

    def test_restart_creates_distinct_identity(self):
        first = sample()
        second = sample()
        second["start_timestamp"] += 100
        self.assertNotEqual(list(make_records(first, "speedtest01"))[0][1],
                            list(make_records(second, "speedtest01"))[0][1])

    def test_conflicting_interval_rolls_back(self):
        self.write(sample())
        import_file(self.db, self.src, "speedtest01")
        changed = sample()
        changed["data_records"][0]["average"]["delivered"]["tx_ip_rate_mbps"] = 999
        self.write(changed)
        with self.assertRaisesRegex(ValueError, "collision"):
            import_file(self.db, self.src, "speedtest01")
        self.assertEqual(len(Storage(self.db).list_measurements()), 1)

    def test_invalid_json_does_not_modify_db(self):
        self.src.write_text("{invalid", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            import_file(self.db, self.src, "speedtest01")
        self.assertFalse(self.db.exists())

    def test_missing_interval_time(self):
        data = sample()
        del data["data_records"][0]["end_datetime"]
        self.write(data)
        with self.assertRaisesRegex(ValueError, "end_datetime"):
            import_file(self.db, self.src, "speedtest01")
        self.assertFalse(self.db.exists())

    def test_missing_server_identity(self):
        with self.assertRaisesRegex(ValueError, "server_id"):
            list(make_records(sample(), ""))


if __name__ == "__main__":
    unittest.main()
