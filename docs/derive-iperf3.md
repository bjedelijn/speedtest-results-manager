# Offline iPerf3 result derivation

First import a structured `iperf3.service` journal export using
`python3 -m results_manager.import_journal`.

Then run:

```bash
python3 -m results_manager.derive_iperf3 \
  --db ./results-dev.sqlite3 --server-id speedtest01
```

The derivation reads previously stored journal events in insertion order and
creates idempotent `iperf3_result` records. Each result retains its source
journal cursor and UTC timestamp.

**Conservative client attribution:** a client IP is assigned only if one
connection was observed in the current boot/PID stream and no abort occurred.
When there are multiple candidates, no candidate, or an abort, the result is
explicitly unattributed. This is not a guarantee that a single candidate
proves session identity.

**Limitations:** this prototype replays all stored events and materializes
each summary independently. It does not yet reconstruct complete tests,
pair sender/receiver summaries, handle concurrent sessions definitively,
or safely paginate large journals. Legacy UDPST session reconstruction
requires additional session identifiers before client-specific materialization.

No live service or router is contacted. No speedtest is initiated.
