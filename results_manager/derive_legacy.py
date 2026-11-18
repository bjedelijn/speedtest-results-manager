"""Conservative UDPST Legacy derivation from stored journal events.

Only isolated, complete sessions are materialized. Overlap is not guessed.
"""
import argparse
import json
import sys

from .parsers import LEGACY_SETUP, LEGACY_INTERVAL, LEGACY_SUMMARY, LEGACY_MAX, parse_udpst_legacy
from .storage import Storage


def derive_legacy(database, server_id):
    if not isinstance(server_id, str) or not server_id.strip() or ":" in server_id:
        raise ValueError("invalid server_id")
    db = Storage(database)
    db.initialize()
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT source_key, payload_json FROM measurements WHERE source=? ORDER BY id",
            ("journal_udpst_legacy",),
        ).fetchall()
    events = []
    for key, payload in rows:
        if not key.startswith(server_id + ":"):
            continue
        event = json.loads(payload)
        if key != server_id + ":" + event["cursor"]:
            raise ValueError("stored event identity mismatch")
        events.append(event)

    records = []
    active = None
    ambiguous = False
    for event in events:
        msg = event["message"]
        setup = LEGACY_SETUP.search(msg)
        if setup:
            # An overlapping setup makes both sessions ambiguous. Wait for
            # a clean process restart before accepting new candidates.
            if active is not None:
                ambiguous = True
                active = None
            elif not ambiguous:
                active = [event]
            continue
        if "Server listening" in msg or "Starting UDPST" in msg:
            active = None
            ambiguous = False
            continue
        if ambiguous or active is None:
            continue
        active.append(event)
        if LEGACY_MAX.search(msg):
            lines = [item["message"] for item in active]
            parsed = list(parse_udpst_legacy(lines))
            if (len(parsed) == 1 and parsed[0]["status"] == "complete"
                    and parsed[0]["summary"] is not None):
                result = parsed[0]
                result.update({
                    "kind": "test_summary",
                    "server_id": server_id,
                    "started_at_utc": active[0]["timestamp_utc"],
                    "ended_at_utc": event["timestamp_utc"],
                    "journal_start_cursor": active[0]["cursor"],
                    "journal_end_cursor": event["cursor"],
                    "attribution": "isolated_candidate",
                })
                records.append(("udpst_legacy_result",
                                server_id + ":" + active[0]["cursor"], result))
            active = None

    if not records:
        return {"inserted": 0, "duplicates": 0, "cursor": None}
    return db.ingest_batch("derived:udpst-legacy:" + server_id,
                           records, records[-1][1])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Derive isolated UDPST Legacy sessions offline")
    parser.add_argument("--db", required=True)
    parser.add_argument("--server-id", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(derive_legacy(args.db, args.server_id)))
    except (OSError, ValueError, TypeError) as exc:
        print("Derivation failed: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
