import unittest
from results_manager.correlation import correlate_iperf3


def event(message, pid="661", boot="boot1"):
    return {"message": message, "pid": pid, "boot_id": boot,
            "cursor": "synthetic", "timestamp_us": 1}


SUMMARY = "[  5] 0.00-10.00 sec 300 MBytes 251 Mbits/sec receiver"


class CorrelationTests(unittest.TestCase):
    def test_single_candidate(self):
        items = [
            event("Accepted connection from 2001:db8::1, port 50001"),
            event(SUMMARY),
        ]
        result = list(correlate_iperf3(items))[0]
        self.assertEqual(result["client_ip"], "2001:db8::1")
        self.assertEqual(result["client_port"], 50001)
        self.assertEqual(result["attribution"], "single_candidate")

    def test_multiple_connections_fail_closed(self):
        items = [
            event("Accepted connection from 192.0.2.1, port 50001"),
            event("Accepted connection from 192.0.2.2, port 50002"),
            event(SUMMARY),
        ]
        result = list(correlate_iperf3(items))[0]
        self.assertIsNone(result["client_ip"])
        self.assertEqual(result["attribution_reason"], "multiple_connections")

    def test_no_connection_fail_closed(self):
        result = list(correlate_iperf3([event(SUMMARY)]))[0]
        self.assertEqual(result["attribution_reason"], "no_connection")

    def test_aborted_fail_closed(self):
        result = list(correlate_iperf3([
            event("Accepted connection from 192.0.2.1, port 50001"),
            event("iperf3: the client has terminated"),
            event(SUMMARY),
        ]))[0]
        self.assertEqual(result["attribution_reason"], "aborted")

    def test_pid_isolation(self):
        result = list(correlate_iperf3([
            event("Accepted connection from 192.0.2.1, port 50001", pid="10"),
            event(SUMMARY, pid="11"),
        ]))[0]
        self.assertIsNone(result["client_ip"])

    def test_boot_isolation(self):
        result = list(correlate_iperf3([
            event("Accepted connection from 192.0.2.1, port 50001", boot="old"),
            event(SUMMARY, boot="new"),
        ]))[0]
        self.assertIsNone(result["client_ip"])

    def test_server_restart_resets(self):
        result = list(correlate_iperf3([
            event("Accepted connection from 192.0.2.1, port 50001"),
            event("Server listening on 5201"),
            event(SUMMARY),
        ]))[0]
        self.assertEqual(result["attribution_reason"], "no_connection")


if __name__ == "__main__":
    unittest.main()
