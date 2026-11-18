# UDPST Modern: offline database import prototype

This is an **explicitly invoked, offline** importer. It does not connect to
journald, run a daemon, modify UDPST, or expose an API.

Run unit tests:

```bash
python3 -m unittest discover -s tests -v
```

Example with an **existing** local copy of stats.json:

```bash
python3 -m results_manager.import_stats --db ./results-dev.sqlite3 --server-id speedtest01 ./stats.json
```

The importer writes JSON metrics into the SQLite prototype. Importing the
same unchanged file twice should return one inserted row and then one
duplicate for a single-record file. Appending a new interval should insert
only that interval.

Records are **server-wide statistics**. They must not be exposed as
per-client throughput results. The uniqueness key uses server identity,
server start timestamp, control port and interval timestamps. A changed
payload for an existing key fails rather than silently overwriting data.

## Still required before production

- Read a consistent file snapshot during UDPST writes and handle transient
  partial JSON without losing progress.
- Confirm that start_timestamp and interval timestamps are stable across
  the real server's rotation/restart behavior.
- Decide retention, privacy, final database engine and migration strategy.
- Add safe periodic synchronization and an authenticated API.
- Implement proper iPerf3/legacy session correlation before importing their
  test results.
