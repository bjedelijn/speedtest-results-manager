# UDPST Legacy offline derivation (experimental)

Import a structured `udpst-legacy.service` journal export first:

```bash
python3 -m results_manager.import_journal --db ./results-dev.sqlite3 \
  --server-id speedtest01 --service udpst-legacy ./legacy-journal.jsonl
```

Then derive candidate complete sessions:

```bash
python3 -m results_manager.derive_legacy \
  --db ./results-dev.sqlite3 --server-id speedtest01
```

The derivation stores `udpst_legacy_result` rows for sessions with setup,
summary and maximum records. Intervals are included where available.
Source journal cursors and UTC timestamps are retained. A second derivation
pass is idempotent for unchanged input.

**Important limitations:** This is a conservative first-pass heuristic, not
verified multi-client correlation. Once overlapping setup requests are
observed, materialization is suspended until a process reset or recognized
listening marker. A process identity change also resets session state.
The parser currently does not associate every sub-interval with a protocol
connection marker; interleaved data may therefore still be misassociated
when overlap is not visible in the available logs. Do not use these results
for customer-facing reporting or SLA decisions until validated against real
anonymized log sequences.

No production deployment, service restart, or new speedtest is performed.
