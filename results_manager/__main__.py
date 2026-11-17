"""Offline JSONL converter. No database, services, or network access."""
import argparse
import json
import sys
from pathlib import Path
from .parsers import parse_iperf3, parse_udpst_legacy, parse_udpst_stats


def main():
    parser = argparse.ArgumentParser(description="Parse existing speedtest data into JSONL (read-only)")
    parser.add_argument("source", choices=("iperf3", "udpst-legacy", "udpst-stats"))
    parser.add_argument("file", help="Input file exported from journald, or stats.json")
    args = parser.parse_args()
    path = Path(args.file)
    try:
        if args.source == "udpst-stats":
            with path.open(encoding="utf-8") as handle:
                records = parse_udpst_stats(json.load(handle))
                for record in records:
                    print(json.dumps(record, ensure_ascii=False))
        else:
            fn = parse_iperf3 if args.source == "iperf3" else parse_udpst_legacy
            with path.open(encoding="utf-8") as handle:
                for record in fn(handle):
                    print(json.dumps(record, ensure_ascii=False))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
