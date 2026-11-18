# Offline journald import prototype

The importer stores **raw, structured journal events** first. It does not
claim they are complete customer speedtests. Session reconstruction and
correlation are a separate, subsequent step.

For an existing local export (do not commit production logs):

```bash
python3 -m results_manager.import_journal \
  --db ./results-dev.sqlite3 --server-id speedtest01 \
  --service iperf3 ./iperf3-journal.jsonl
```

Use `--service udpst-legacy` for an export containing only
`udpst-legacy.service` events. Export format must be `journalctl -o json`
with the full structured fields, including `__CURSOR` and
`__REALTIME_TIMESTAMP`. Do not use `-o short`.

For subsequent imports, supply a complete ordered export containing the
previous checkpoint and any newer events. The importer skips through that
checkpoint, then commits all newer events and the final cursor in one SQLite
transaction. Missing checkpoint, malformed input, duplicate cursors, or
unexpected systemd units cause the import to fail closed.

## Limitations / production gates

- **Offline only:** no server access, scheduler, journalctl execution or API.
- Entire export is held in memory; use bounded exports in development.
- Journal checkpoint matching is based on the previous cursor being present.
  Live incremental `--after-cursor` ingestion needs a separate, carefully
  defined trust and recovery model.
- Raw logs can include client IPs and other personal data. Set permissions,
  retention and access controls before any real deployment.
- Parsing a complete export before writing prevents partial imports from
  advancing checkpoints, but does not guarantee an export is exhaustive.
- iPerf3 and UDPST Legacy session correlation is **not yet integrated**.
- This prototype uses the existing measurements table for raw journal events;
  a dedicated journal-events table is advisable before production.
