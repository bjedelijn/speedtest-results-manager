"""Conservative offline derivation of iPerf3 summaries from stored journal events."""
import argparse
import json
import sys

from .correlation import correlate_iperf3
from .parsers import parse_iperf3
from .storage import Storage


def derive_iperf3(database, server_id):
    """Derive summary rows; never infer client identity from ambiguous streams.

    Rebuilds from all retained events in ingestion order. This is a prototype
    for bounded datasets, not a scalable incremental materialization engine.
    """
    if not isinstance(server_id, str) or not server_id.strip() or ":" in server_id:
        raise ValueError("invalid server_id")
    db = Storage(database)
    db.initialize()
    source = "journal_iperf3"
    # Read in ascending insertion order, not reverse display order.
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT source_key, payload_json FROM measurements WHERE source=? "
            "AND source_key LIKE ? ORDER BY id",
            (source, server_id + ":%"),
        ).fetchall()
    events = []
    for key, payload in rows:
        event = json.loads(payload)
        if key != server_id + ":" + event["cursor"]:
            raise ValueError("stored event identity mismatch")
        events.append(event)
    annotated = list(correlate_iperf3(events))
    records = []
    for event in annotated:
        parsed = list(parse_iperf3([event["message"]]))
        if len(parsed) != 1:
            continue
        result = parsed[0]
        result.update({
            "timestamp_utc": event["timestamp_utc"],
            "journal_cursor": event["cursor"],
            "client_ip": event["client_ip"],
            "client_port": event["client_port"],
            "attribution": event["attribution"],
            "attribution_reason": event["attribution_reason"],
            "kind": "test_summary",
            "server_id": server_id,
        })
        records.append(("iperf3_result", server_id + ":" + event["cursor"], result))
    if not records:
        return {"inserted": 0, "duplicates": 0, "cursor": None}
    # Derivation checkpoint is a materialization marker, not a journal cursor.
    return db.ingest_batch("derived:iperf3:" + server_id, records, records[-1][1])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Derive existing iPerf3 journal summaries offline")
    parser.add_argument("--db", required=True)
    parser.add_argument("--server-id", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(derive_iperf3(args.db, args.server_id)))
    except (OSError, ValueError, TypeError) as exc:
        print("Derivation failed: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
