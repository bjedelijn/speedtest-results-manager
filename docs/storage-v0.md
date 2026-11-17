# SQLite storage prototype

The storage module is an **offline development component**, not a running
service on speedtest01. It uses Python's standard-library sqlite3 and requires
no database server or third-party packages.

```bash
python3 -m unittest discover -s tests -v
```

`Storage(path).initialize()` creates tables in the explicitly supplied local
SQLite file. `ingest_batch(stream, records, cursor)` accepts
`(source, stable_source_key, payload)` tuples and commits both rows and
the checkpoint atomically. Replayed identical records are ignored; a reused
key with different contents fails and rolls back the whole batch.

## Important limitations before production

- There is no automatic journald ingestion, sync scheduler or API yet.
- Checkpoints must represent the **last fully processed event**; a partially
  assembled test must not be acknowledged prematurely.
- This schema stores generic normalized JSON, not final per-test/per-interval
  relational tables.
- Stable keys for test sessions must be based on actual source identity;
  content hashes alone do not identify separate identical tests.
- Journald cursors are stream positions, not measurement identifiers.
- Concurrency, journal vacuum gaps, replay recovery and retention need
  integration testing before production use.
- SQLite is a prototype choice, **not** a decision about the final DB engine.
