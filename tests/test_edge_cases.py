"""Regression tests using synthetic, non-customer data."""
import unittest

from results_manager.parsers import parse_iperf3, parse_udpst_legacy, parse_udpst_stats


class IperfEdgeCases(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(list(parse_iperf3([])), [])

    def test_receiver_and_rate_units(self):
        lines = [
            "Accepted connection from 192.0.2.12, port 45678",
            "[  5]   0.00-10.00 sec 1.00 GBytes 1.25 Gbits/sec receiver",
        ]
        result = list(parse_iperf3(lines))[0]
        self.assertEqual(result["client_ip"], "192.0.2.12")
        self.assertEqual(result["direction_server"], "receiver")
        self.assertEqual(result["bitrate_mbps"], 1250.0)
        self.assertIsNone(result["retransmits"])

    def test_invalid_duration_is_not_capacity(self):
        lines = ["[  5] 0.00-7218850.28 sec 104 MBytes 121 bits/sec receiver"]
        result = list(parse_iperf3(lines))[0]
        self.assertEqual(result["status"], "invalid_duration")
        self.assertIsNone(result["bitrate_mbps"])


class LegacyEdgeCases(unittest.TestCase):
    def test_incomplete_session_is_retained(self):
        lines = [
            "[1]Setup request (Ver: 9, MaxBW: 0) received from 2001:db8::10:48978",
            "[2]Sub-Interval[1](sec): 1, Delivered(%): 100.00, Loss/OoO/Dup: 0/0/0, OWDVar(ms): 0/1/16, RTTVar(ms): 0-5, Mbps(L3/IP): 90.79",
        ]
        result = list(parse_udpst_legacy(lines))[0]
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["client_ip"], "2001:db8::10")
        self.assertEqual(result["client_port"], 48978)

    def test_empty_input(self):
        self.assertEqual(list(parse_udpst_legacy([])), [])


class ModernStatsEdgeCases(unittest.TestCase):
    def test_invalid_schema(self):
        with self.assertRaises(ValueError):
            list(parse_udpst_stats({"data_records": {}}))

    def test_empty_records(self):
        self.assertEqual(list(parse_udpst_stats({"data_records": []})), [])

    def test_preserves_server_metrics(self):
        data = {
            "software_version": "9.1.0",
            "protocol_version": 20,
            "schema_version": 1.0,
            "data_records": [{
                "start_datetime": "2026-11-17T22:38:44+01:00",
                "end_datetime": "2026-11-17T22:38:54+01:00",
                "maximum": {"allocated": {"connection_count": 2}},
                "average": {"delivered": {"tx_ip_rate_mbps": 250.0}},
            }],
        }
        result = list(parse_udpst_stats(data))[0]
        self.assertEqual(result["kind"], "server_statistics")
        self.assertEqual(result["maximum"]["allocated"]["connection_count"], 2)
        self.assertEqual(result["average"]["delivered"]["tx_ip_rate_mbps"], 250.0)


if __name__ == "__main__":
    unittest.main()
