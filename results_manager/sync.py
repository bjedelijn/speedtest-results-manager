"""Explicit offline synchronization of existing speedtest exports.

Never runs speedtests, journalctl, or service management commands.
"""
import argparse
import json
import sys

from .derive_iperf3 import derive_iperf3
from .derive_legacy import derive_legacy
from .import_journal import import_journal
from .import_stats import import_file


def sync_existing(database, server_id, *, iperf3=None, legacy=None, modern=None):
    """Import selected existing files, then derive results from stored events.

    Each source commits independently. This is NOT an all-or-nothing sync
    across sources; failures are reported and later runs are safe to retry.
    """
    if not isinstance(server_id, str) or not server_id.strip() or ":" in server_id:
        raise ValueError("invalid server_id")
    if not any((iperf3, legacy, modern)):
        raise ValueError("at least one existing source file must be supplied")
    results = {}
    if modern is not None:
        results["udpst_modern_stats"] = import_file(database, modern, server_id)
    if iperf3 is not None:
        results["iperf3_journal"] = import_journal(database, iperf3, server_id, "iperf3")
        results["iperf3_results"] = derive_iperf3(database, server_id)
    if legacy is not None:
        results["udpst_legacy_journal"] = import_journal(database, legacy, server_id, "udpst-legacy")
        results["udpst_legacy_results"] = derive_legacy(database, server_id)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline sync of existing speedtest exports")
    parser.add_argument("--db", required=True)
    parser.add_argument("--server-id", required=True)
    parser.add_argument("--iperf3-journal", help="Existing structured JSONL export")
    parser.add_argument("--legacy-journal", help="Existing structured JSONL export")
    parser.add_argument("--modern-stats", help="Existing stats.json snapshot")
    args = parser.parse_args(argv)
    try:
        result = sync_existing(args.db, args.server_id, iperf3=args.iperf3_journal,
                               legacy=args.legacy_journal, modern=args.modern_stats)
        print(json.dumps(result, sort_keys=True))
    except (OSError, ValueError, TypeError) as exc:
        print("Sync failed: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
