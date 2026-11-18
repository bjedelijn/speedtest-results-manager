"""Offline, idempotent import of UDPST server-wide statistics into SQLite."""
import argparse
import json
import sys
from pathlib import Path

from .parsers import parse_udpst_stats
from .storage import Storage
from .snapshot import read_stable_json, UnstableSnapshotError


def make_records(data, server_id):
    """Stable interval identity scoped to server, restart and protocol."""
    if not isinstance(server_id, str) or not server_id.strip():
        raise ValueError("server_id is required")
    start = data.get("start_timestamp")
    if not isinstance(start, (int, float)) or isinstance(start, bool):
        raise ValueError("stats file must include a numeric server start_timestamp")
    for record in parse_udpst_stats(data):
        begin = record.get("start_datetime")
        end = record.get("end_datetime")
        if not isinstance(begin, str) or not begin or not isinstance(end, str) or not end:
            raise ValueError("each statistics interval requires start_datetime and end_datetime")
        key = json.dumps(
            [server_id, start, data.get("control_port"), begin, end],
            separators=(",", ":"), ensure_ascii=False,
        )
        yield ("udpst_modern_stats", key, record)


def import_file(database, filename, server_id):
    """Parse fully before transaction; no changes if JSON is malformed."""
    data = read_stable_json(filename)
    if not isinstance(data, dict):
        raise ValueError("stats root must be an object")
    records = list(make_records(data, server_id))
    db = Storage(database)
    db.initialize()
    # Stats files are snapshots, not journals; a synthetic checkpoint only
    # describes the last successfully imported snapshot, never a journal cursor.
    checkpoint = json.dumps(
        [data.get("start_timestamp"), len(records),
         records[-1][1] if records else None], separators=(",", ":")
    )
    return db.ingest_batch("udpst-modern-stats:" + server_id, records, checkpoint)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Import existing UDPST stats JSON (offline)")
    parser.add_argument("--db", required=True, help="SQLite database file to create/update")
    parser.add_argument("--server-id", required=True, help="Stable server identifier, e.g. speedtest01")
    parser.add_argument("file", help="Existing UDPST stats.json")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(import_file(args.db, args.file, args.server_id)))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print("Import failed: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
