# Offline collector prototype

This is an experimental read-only parser. It does not install a daemon, change running services, write to a database, or expose an API.

## Test

```bash
python3 -m unittest discover -s tests -v
```

## Parse exported logs

```bash
journalctl -u iperf3 --since "24 hours ago" --no-pager -o short > /tmp/iperf3.log
python3 -m results_manager iperf3 /tmp/iperf3.log
journalctl -u udpst-legacy --since "24 hours ago" --no-pager -o short > /tmp/udpst-legacy.log
python3 -m results_manager udpst-legacy /tmp/udpst-legacy.log
python3 -m results_manager udpst-stats /var/lib/udpst/stats.json
```

Output is JSON Lines on stdout. Do not commit exported logs or output containing client IP addresses.

## Known limitations

- Legacy test correlation assumes sequential sessions; interleaved sessions need connection-ID correlation.
- iPerf3 parser extracts summary lines, not full multi-stream test sessions.
- Abnormal iPerf3 durations are marked invalid and excluded from bitrate.
- Human-readable journal timestamps omit year and timezone; structured journald timestamps are required before database ingestion.
- Modern UDPST JSON provides server statistics, not confirmed per-client test results.
- No persistent cursor, deduplication, database, synchronization API, or production service yet.
- This prototype should not be deployed as an unattended production collector.
