"""Read structured journalctl JSON lines without changing system state."""
import json
from datetime import datetime, timezone


def parse_journal_json(lines):
    """Yield normalized journal events with UTC timestamps and stable cursors.

    journalctl -o json emits one object per line. Missing/malformed timestamps
    fail closed rather than assigning the current time.
    """
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid journal JSON at line {number}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"Journal entry {number} is not an object")
        raw_ts = obj.get("__REALTIME_TIMESTAMP")
        if not isinstance(raw_ts, str) or not raw_ts.isdecimal():
            raise ValueError(f"Journal entry {number} has no valid realtime timestamp")
        message = obj.get("MESSAGE")
        if not isinstance(message, str):
            raise ValueError(f"Journal entry {number} has no string MESSAGE")
        cursor = obj.get("__CURSOR")
        if not isinstance(cursor, str) or not cursor:
            raise ValueError(f"Journal entry {number} has no cursor")
        instant = datetime.fromtimestamp(int(raw_ts) / 1_000_000, tz=timezone.utc)
        yield {
            "timestamp_utc": instant.isoformat(),
            "timestamp_us": int(raw_ts),
            "cursor": cursor,
            "boot_id": obj.get("_BOOT_ID"),
            "message": message,
        }
