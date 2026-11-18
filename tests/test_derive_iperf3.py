import json
import tempfile
import unittest
from pathlib import Path

from results_manager.derive_iperf3 import derive_iperf3
from results_manager.import_journal import import_journal
from results_manager.storage import Storage


def event(cursor, message):
    return {"__CURSOR": cursor, "__REALTIME_TIMESTAMP": "1795000000000000",
            "MESSAGE": message, "_SYSTEMD_UNIT": "iperf3.service",
            "_BOOT_ID": "synthetic-boot", "_PID": "42"}


SUMMARY = "[  5]   0.00-10.00 sec  100 MBytes  83.9 Mbits/sec  receiver"


class DerivedIperfTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "db.sqlite3"
        self.src = Path(self.tmp.name) / "events.jsonl"

    def load(self, entries):
        self.src.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
        import_journal(self.db, self.src, "speedtest01", "iperf3")

    def results(self):
        return Storage(self.db).list_measurements(source="iperf3_result")

    def test_single_connection_and_idempotence(self):
        self.load([event("a", "Server listening on 5201"),
                   event("b", "Accepted connection from 192.0.2.5, port 40001"),
                   event("c", SUMMARY)])
        self.assertEqual(derive_iperf3(self.db, "speedtest01")["inserted"], 1)
        self.assertEqual(derive_iperf3(self.db, "speedtest01")["duplicates"], 1)
        result = self.results()[0]["payload"]
        self.assertEqual(result["client_ip"], "192.0.2.5")
        self.assertEqual(result["attribution"], "single_candidate")
        self.assertEqual(result["bitrate_mbps"], 83.9)
        self.assertEqual(result["journal_cursor"], "c")

    def test_parallel_clients_unattributed(self):
        self.load([event("a", "Accepted connection from 192.0.2.5, port 40001"),
                   event("b", "Accepted connection from 192.0.2.6, port 40002"),
                   event("c", SUMMARY)])
        derive_iperf3(self.db, "speedtest01")
        result = self.results()[0]["payload"]
        self.assertIsNone(result["client_ip"])
        self.assertEqual(result["attribution_reason"], "multiple_connections")

    def test_abort_unattributed(self):
        self.load([event("a", "Accepted connection from 192.0.2.5, port 40001"),
                   event("b", "iperf3: error - the client has terminated"),
                   event("c", SUMMARY)])
        derive_iperf3(self.db, "speedtest01")
        self.assertEqual(self.results()[0]["payload"]["attribution_reason"], "aborted")

    def test_no_summary_does_not_materialize(self):
        self.load([event("a", "Accepted connection from 192.0.2.5, port 40001")])
        self.assertEqual(derive_iperf3(self.db, "speedtest01")["inserted"], 0)
        self.assertEqual(self.results(), [])


if __name__ == "__main__":
    unittest.main()
