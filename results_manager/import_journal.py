"""Offline ingestion of structured journald exports; never starts measurements."""
import argparse
import json
import sys
from pathlib import Path

from .journal import parse_journal_json
from .storage import Storage

UNITS = {
    "iperf3": "iperf3.service",
    "udpst-legacy": "udpst-legacy.service",
}


def import_journal(database, filename, server_id, service):
    """Import a complete, ordered JSONL export with restart-safe checkpointing.

    Existing checkpoints must appear in the supplied export. This intentionally
    rejects truncated or unrelated exports rather than rewinding a checkpoint.
    """
    if not isinstance(server_id, str) or not server_id.strip() or ":" in server_id:
        raise ValueError("server_id must be nonempty and cannot contain ':'")
    if service not in UNITS:
        raise ValueError("unknown service")
    stream = "journal:" + server_id + ":" + service
    db = Storage(database)
    # Parse and validate entire export before creating a database.
    with Path(filename).open(encoding="utf-8") as source:
        events = list(parse_journal_json(source))
    seen = set()
    for event in events:
        if event["unit"] != UNITS[service]:
            raise ValueError("journal export contains an unexpected systemd unit")
        if event["cursor"] in seen:
            raise ValueError("journal export contains duplicate cursors")
        seen.add(event["cursor"])
    db.initialize()
    previous = db.checkpoint(stream)
    if previous is not None:
        indices = [i for i, e in enumerate(events) if e["cursor"] == previous]
        if not indices:
            raise ValueError("checkpoint cursor absent from export; refusing to rewind")
        events = events[indices[0] + 1:]
    if not events:
        return {"inserted": 0, "duplicates": 0, "cursor": previous}
    records = [
        ("journal_" + service.replace("-", "_"),
         server_id + ":" + event["cursor"], event)
        for event in events
    ]
    return db.ingest_batch(stream, records, events[-1]["cursor"])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Import existing structured journald JSONL offline")
    parser.add_argument("--db", required=True)
    parser.add_argument("--server-id", required=True)
    parser.add_argument("--service", required=True, choices=sorted(UNITS))
    parser.add_argument("file", help="Complete journalctl -o json export including prior cursor")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(import_journal(args.db, args.file, args.server_id, args.service)))
    except (OSError, ValueError, TypeError) as exc:
        print("Import failed: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
