# Journald synchronization design (not yet deployed)

Use `journalctl -u iperf3 -o json --no-pager` and the corresponding
`udpst-legacy` unit for **structured timestamps and cursors**. The pure
`results_manager.journal.parse_journal_json` parser validates individual
events and normalizes timestamps to UTC.

## Cursor and transaction rules

- Maintain a checkpoint per machine, boot-independent journal stream and unit.
- Read entries after the last committed cursor. The cursor is opaque.
- Commit parsed measurements and checkpoint **in the same database transaction**.
- Use unique source identifiers to make replays idempotent.
- If a cursor expires because of journal vacuuming, record an explicit gap and
  backfill from available retained records; never silently claim complete history.
- A partial UDPST test at the end of a batch must remain pending across batches.
- Do not treat server-wide UDPST JSON statistics as individual speed tests.
- Read `stats.json` as a stable snapshot; deduplicate snapshots using a source
  identity and interval timestamps, not just file modification time.

## Safety

This document describes the next implementation stage, not an enabled
synchronization service. A live collector must have minimal journal access,
bounded memory and CPU, backpressure, authentication on any API, and must never
restart or reconfigure the existing test services.
