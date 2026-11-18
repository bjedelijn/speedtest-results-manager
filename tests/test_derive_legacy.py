import json
import tempfile
import unittest
from pathlib import Path

from results_manager.derive_legacy import derive_legacy
from results_manager.import_journal import import_journal
from results_manager.storage import Storage

SETUP = "Setup request [1] received from 192.0.2.10:42000"
INTERVAL = ("Sub-Interval[1] Delivered(%): 95.73, Loss/OoO/Dup: 1/0/0, "
            "OWDVar(ms): 0/34/123, RTTVar(ms): 0-113, Mbps(L3/IP): 461.61")
SUMMARY = ("Downstream Summary Delivered(%): 95.73, Loss/OoO/Dup: 1/0/0, "
           "Mbps(L3/IP): 461.61")
MAXIMUM = ("Downstream Maximum Mbps(L3/IP): 529.01, Mbps(L2/Eth): 535.00, "
           "Mbps(L1/Eth): 545.26, Mbps(L1/Eth+VLAN): 546.97")


def event(cursor, message):
    return {"__CURSOR": cursor, "__REALTIME_TIMESTAMP": "1795000000000000",
            "MESSAGE": message, "_SYSTEMD_UNIT": "udpst-legacy.service",
            "_BOOT_ID": "synthetic-boot", "_PID": "123"}


class LegacyDerivationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "db.sqlite3"
        self.file = Path(tmp.name) / "journal.jsonl"

    def load(self, entries):
        self.file.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
        import_journal(self.db, self.file, "speedtest01", "udpst-legacy")

    def results(self):
        return Storage(self.db).list_measurements(source="udpst_legacy_result")

    def test_isolated_complete_session(self):
        self.load([event("a", SETUP), event("b", INTERVAL),
                   event("c", SUMMARY), event("d", MAXIMUM)])
        self.assertEqual(derive_legacy(self.db, "speedtest01")["inserted"], 1)
        self.assertEqual(derive_legacy(self.db, "speedtest01")["duplicates"], 1)
        record = self.results()[0]["payload"]
        self.assertEqual(record["client_ip"], "192.0.2.10")
        self.assertEqual(record["journal_end_cursor"], "d")
        self.assertEqual(record["summary"]["ip_mbps"], 461.61)

    def test_incomplete_is_not_materialized(self):
        self.load([event("a", SETUP), event("b", INTERVAL)])
        self.assertEqual(derive_legacy(self.db, "speedtest01")["inserted"], 0)

    def test_overlapping_setups_are_not_attributed(self):
        self.load([event("a", SETUP),
                   event("b", "Setup request [2] received from 192.0.2.11:42001"),
                   event("c", INTERVAL), event("d", SUMMARY), event("e", MAXIMUM)])
        self.assertEqual(derive_legacy(self.db, "speedtest01")["inserted"], 0)

    def test_summary_without_setup_is_not_materialized(self):
        self.load([event("a", SUMMARY), event("b", MAXIMUM)])
        self.assertEqual(derive_legacy(self.db, "speedtest01")["inserted"], 0)


if __name__ == "__main__":
    unittest.main()
