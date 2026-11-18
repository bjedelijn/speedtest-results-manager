# Unified offline synchronization prototype

The command combines the existing importers and derivation steps. It does
**not** access the live server, start a test, invoke journalctl or modify
existing speedtest services.

With existing local exports:

```bash
python3 -m results_manager.sync --db ./results-dev.sqlite3 \
  --server-id speedtest01 \
  --iperf3-journal ./iperf3.jsonl \
  --legacy-journal ./legacy.jsonl \
  --modern-stats ./stats.json
```

All three source arguments are optional individually, but at least one is
required. Journal exports must contain the previous stored checkpoint
cursor on subsequent runs. The modern statistics file is imported as
server-wide metrics, not customer tests.

Each source commits independently; a later failure does not roll back an
earlier successful source. Re-running with the same complete inputs is
designed to be idempotent. A missing checkpoint in a journal export is
treated as an error rather than an implicit rewind.

## Before automatic sync or HTTP API

- Add bounded live journal reading with explicit cursor resume/recovery.
- Validate Legacy session correlation with anonymized production patterns.
- Define authenticated, read-only result API and separate explicit sync trigger.
- Add retention and access controls for client IPs and raw log messages.
- Add pagination and a dedicated journal-events table for larger datasets.
- Confirm CI and integration tests before deployment.
