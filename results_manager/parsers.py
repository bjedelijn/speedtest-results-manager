"""Pure parsers for existing speedtest logs. No system or network access."""
import json
import re
from datetime import datetime

PREFIX = re.compile(r"^(?P<time>[A-Z][a-z]{2} +\d+ \d\d:\d\d:\d\d) \S+ \S+\[\d+\]: (?P<msg>.*)$")
IPERF_CONNECT = re.compile(r"Accepted connection from (?P<client>\S+), port (?P<port>\d+)")
IPERF_SUMMARY = re.compile(r"\[\s*\d+\]\s+(?P<start>[\d.]+)-(?P<end>[\d.]+)\s+sec\s+(?P<amount>[\d.]+)\s+(?P<unit>[KMG]?Bytes)\s+(?P<rate>[\d.]+)\s+(?P<rate_unit>[KMG]?bits/sec)(?P<rest>.*)")
LEGACY_SETUP = re.compile(r"Setup request .* received from (?P<client>\S+):(?P<port>\d+)")
LEGACY_INTERVAL = re.compile(r"Sub-Interval\[(?P<n>\d+)\].*?Delivered\(%\):\s*(?P<delivered>[\d.]+), Loss/OoO/Dup:\s*(?P<loss>\d+)/(?P<ooo>\d+)/(?P<dup>\d+), OWDVar\(ms\):\s*(?P<owd>\d+/\d+/\d+), RTTVar\(ms\):\s*(?P<rtt>\d+-\d+), Mbps\(L3/IP\):\s*(?P<mbps>[\d.]+)")
LEGACY_SUMMARY = re.compile(r"Downstream Summary Delivered\(%\):\s*(?P<delivered>[\d.]+), Loss/OoO/Dup:\s*(?P<loss>\d+)/(?P<ooo>\d+)/(?P<dup>\d+).*?Mbps\(L3/IP\):\s*(?P<mbps>[\d.]+)")
LEGACY_MAX = re.compile(r"Downstream Maximum Mbps\(L3/IP\):\s*(?P<ip>[\d.]+), Mbps\(L2/Eth\):\s*(?P<eth>[\d.]+), Mbps\(L1/Eth\):\s*(?P<l1>[\d.]+), Mbps\(L1/Eth\+VLAN\):\s*(?P<vlan>[\d.]+)")


def messages(lines):
    for line in lines:
        match = PREFIX.match(line.rstrip("\n"))
        if match:
            yield match.group("time"), match.group("msg")
        else:
            # Also accepts raw service output, without syslog prefixes.
            yield None, line.rstrip("\n")


def parse_iperf3(lines):
    """Emit completed summaries and flagged invalid/interrupted summaries.

    This is a first-pass log parser, not a guaranteed correlation of parallel streams.
    """
    client = None
    for timestamp, msg in messages(lines):
        if "Server listening on " in msg:
            client = None
        match = IPERF_CONNECT.search(msg)
        if match:
            client = match.group("client")
        match = IPERF_SUMMARY.search(msg)
        if not match or not re.search(r"\b(sender|receiver)\s*$", msg):
            continue
        duration = float(match.group("end")) - float(match.group("start"))
        rate = float(match.group("rate"))
        unit = match.group("rate_unit")
        valid = 0 < duration <= 3600 and rate >= 0
        bits_per_second = rate * {"bits/sec": 1, "Kbits/sec": 1e3, "Mbits/sec": 1e6, "Gbits/sec": 1e9}[unit]
        retransmits = re.search(r"\s(\d+)\s+sender\s*$", msg)
        yield {
            "source": "iperf3", "timestamp": timestamp, "client_ip": client,
            "direction_server": msg.strip().split()[-1],
            "duration_seconds": round(duration, 3),
            "bitrate_mbps": round(bits_per_second / 1e6, 6) if valid else None,
            "retransmits": int(retransmits.group(1)) if retransmits else None,
            "status": "complete" if valid else "invalid_duration",
            "raw": msg,
        }


def parse_udpst_legacy(lines):
    """Emit one test summary with intervals; incomplete sessions are marked.

    Legacy output shown in production uses connection markers [1]/[2].
    A new setup begins a new session. Only summary-bearing sessions are emitted.
    """
    session = None
    for timestamp, msg in messages(lines):
        setup = LEGACY_SETUP.search(msg)
        if setup:
            if session and session["intervals"]:
                session["status"] = "incomplete"
                yield session
            session = {"source": "udpst_legacy", "started_at": timestamp,
                       "client_ip": setup.group("client"), "client_port": int(setup.group("port")),
                       "intervals": [], "summary": None, "maximum": None, "status": "incomplete"}
            continue
        if session is None:
            continue
        interval = LEGACY_INTERVAL.search(msg)
        if interval:
            g = interval.groupdict()
            session["intervals"].append({
                "index": int(g["n"]), "delivered_percent": float(g["delivered"]),
                "loss_count": int(g["loss"]), "out_of_order_count": int(g["ooo"]),
                "duplicate_count": int(g["dup"]), "ip_mbps": float(g["mbps"]),
                "owd_variation_ms": [int(x) for x in g["owd"].split("/")],
                "rtt_variation_ms": [int(x) for x in g["rtt"].split("-")],
            })
        summary = LEGACY_SUMMARY.search(msg)
        if summary:
            g = summary.groupdict()
            session["summary"] = {
                "delivered_percent": float(g["delivered"]), "loss_count": int(g["loss"]),
                "out_of_order_count": int(g["ooo"]), "duplicate_count": int(g["dup"]),
                "ip_mbps": float(g["mbps"]),
            }
        maximum = LEGACY_MAX.search(msg)
        if maximum:
            session["maximum"] = {key + "_mbps": float(value) for key, value in maximum.groupdict().items()}
            session["status"] = "complete" if session["summary"] else "incomplete"
            session["ended_at"] = timestamp
            yield session
            session = None
    if session and session["intervals"]:
        session["status"] = "incomplete"
        yield session


def parse_udpst_stats(data):
    """Return server-wide snapshots, never label them as customer tests."""
    if not isinstance(data, dict) or not isinstance(data.get("data_records"), list):
        raise ValueError("UDPST statistics must contain a data_records array")
    for record in data["data_records"]:
        if not isinstance(record, dict):
            continue
        yield {
            "source": "udpst_modern", "kind": "server_statistics",
            "software_version": data.get("software_version"),
            "protocol_version": data.get("protocol_version"),
            "schema_version": data.get("schema_version"),
            "start_datetime": record.get("start_datetime"),
            "end_datetime": record.get("end_datetime"),
            "maximum": record.get("maximum"),
            "average": record.get("average"),
        }
