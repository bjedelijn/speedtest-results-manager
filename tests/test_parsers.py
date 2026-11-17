import unittest
from results_manager.parsers import parse_iperf3, parse_udpst_legacy, parse_udpst_stats


class ParserTests(unittest.TestCase):
    def test_iperf_valid_and_interrupted(self):
        lines = [
            "Nov 17 22:22:39 speedtest01 iperf3[661]: Accepted connection from 2001:db8::1, port 47242\n",
            "Nov 17 22:22:39 speedtest01 iperf3[661]: [  5]   0.00-10.01  sec   311 MBytes   260 Mbits/sec  147 sender\n",
            "Nov 17 22:36:22 speedtest01 iperf3[661]: [  5]   0.00-7218850.28 sec   104 MBytes   121 bits/sec receiver\n",
        ]
        records = list(parse_iperf3(lines))
        self.assertEqual(records[0]["bitrate_mbps"], 260)
        self.assertEqual(records[0]["retransmits"], 147)
        self.assertEqual(records[0]["client_ip"], "2001:db8::1")
        self.assertEqual(records[1]["status"], "invalid_duration")
        self.assertIsNone(records[1]["bitrate_mbps"])

    def test_legacy_intervals_and_summary(self):
        lines = [
            "[1]Setup request (Ver: 9, MaxBW: 0) received from 2001:db8::2:48978\n",
            "[2]Sub-Interval[1](sec):   1, Delivered(%): 100.00, Loss/OoO/Dup: 0/0/0, OWDVar(ms): 0/1/16, RTTVar(ms): 0-5, Mbps(L3/IP): 90.79\n",
            "[2]Downstream Summary Delivered(%): 95.73, Loss/OoO/Dup: 41712/0/0, OWDVar(ms): 0/34/123, RTTVar(ms): 0-113, Mbps(L3/IP): 461.61\n",
            "[2]Downstream Maximum Mbps(L3/IP): 529.01, Mbps(L2/Eth): 535.00, Mbps(L1/Eth): 545.26, Mbps(L1/Eth+VLAN): 546.97\n",
        ]
        results = list(parse_udpst_legacy(lines))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "complete")
        self.assertEqual(results[0]["summary"]["ip_mbps"], 461.61)
        self.assertEqual(results[0]["maximum"]["ip_mbps"], 529.01)
        self.assertEqual(results[0]["intervals"][0]["ip_mbps"], 90.79)

    def test_stats_are_server_wide(self):
        records = list(parse_udpst_stats({"data_records": [{"start_datetime": "2026-11-17T22:38:44+01:00", "average": {"delivered": {}}}], "protocol_version": 20}))
        self.assertEqual(records[0]["kind"], "server_statistics")
        self.assertEqual(records[0]["protocol_version"], 20)


if __name__ == "__main__":
    unittest.main()
