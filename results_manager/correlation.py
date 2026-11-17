"""Conservative iPerf3 summary attribution from structured journal events.

Ambiguous results are explicitly unattributed, never guessed.
"""
import re

CONNECT = re.compile(r"Accepted connection from (?P<ip>\S+), port (?P<port>\d+)")
SUMMARY = re.compile(r"\[\s*\d+\]\s+(?P<start>\d+(?:\.\d+)?)-(?P<end>\d+(?:\.\d+)?)\s+sec\s+\S+\s+[KMG]?Bytes\s+\S+\s+[KMG]?bits/sec.*\b(?P<direction>sender|receiver)\s*$")
ABORT = re.compile(r"the client has terminated|iperf3: error", re.I)


def correlate_iperf3(events):
    """Yield annotated summary events.

    A summary is attributed only if exactly one connection was observed in
    the current journal boot/PID stream since the last reset. This is a
    conservative candidate, not proof of a complete end-to-end test.
    """
    streams = {}
    for event in events:
        msg = event["message"]
        key = (event.get("boot_id"), event.get("pid"))
        stream = streams.setdefault(key, {"connections": [], "aborted": False})
        if "Server listening on " in msg:
            stream["connections"] = []
            stream["aborted"] = False
            continue
        match = CONNECT.search(msg)
        if match:
            stream["connections"].append((match.group("ip"), int(match.group("port"))))
            continue
        if ABORT.search(msg):
            stream["aborted"] = True
            continue
        match = SUMMARY.search(msg)
        if not match:
            continue
        candidates = stream["connections"]
        confident = len(candidates) == 1 and not stream["aborted"]
        result = dict(event)
        result["direction_server"] = match.group("direction")
        result["client_ip"] = candidates[0][0] if confident else None
        result["client_port"] = candidates[0][1] if confident else None
        result["attribution"] = "single_candidate" if confident else "unattributed"
        result["attribution_reason"] = (
            None if confident else
            "aborted" if stream["aborted"] else
            "no_connection" if not candidates else "multiple_connections"
        )
        yield result
