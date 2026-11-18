"""Read a bounded, stable snapshot of a periodically rewritten JSON file."""
import json
from pathlib import Path


class UnstableSnapshotError(ValueError):
    """The source changed during reading or could not be parsed safely."""


def read_stable_json(path, *, max_bytes=16 * 1024 * 1024, attempts=3):
    """Return parsed JSON only when pre/post file metadata matches.

    No sleeps, locks, or writes. Callers may retry on a later sync cycle.
    Metadata equality does not prove an atomic writer; production deployments
    should also confirm UDPST's file replacement semantics.
    """
    if attempts < 1 or max_bytes < 1:
        raise ValueError("attempts and max_bytes must be positive")
    path = Path(path)
    for _ in range(attempts):
        before = path.stat()
        if before.st_size > max_bytes:
            raise ValueError("statistics file exceeds size limit")
        with path.open("rb") as stream:
            opened = stream.fileno()
            import os
            opened_before = os.fstat(opened)
            raw = stream.read(max_bytes + 1)
            opened_after = os.fstat(opened)
        after = path.stat()
        if len(raw) > max_bytes:
            raise ValueError("statistics file exceeds size limit")
        fingerprint = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if not (fingerprint(before) == fingerprint(opened_before) ==
                fingerprint(opened_after) == fingerprint(after)):
            continue
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise UnstableSnapshotError("statistics file changed or contained incomplete JSON")
