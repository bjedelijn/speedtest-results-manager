# Qonnected Speedtest Results Manager

Optional, independent results collection and synchronization service for Qonnected speedtest infrastructure.

> **Status:** Design / planning (v1). No production installation or database changes are included.

## Scope

- Read existing iPerf3 server logs from journald.
- Read TR-471 UDPST legacy (protocol 8-9) test summaries and sub-intervals from journald.
- Read modern TR-471 UDPST (protocol 11-20) server statistics from the existing JSON statistics file.
- Normalize and validate data, retain raw source records where appropriate, and store results in a database.
- Support periodic incremental synchronization **and** an authenticated, on-demand synchronization request.
- Expose synchronized results and synchronization status to authorized external systems.

**Out of scope:** initiating speed tests, controlling routers/CPE, customer portal implementation, changing iperf3/UDPST services, and firewall/ASN management.

## Confirmed sources on speedtest01

| Source | Existing command / location | What is known |
| --- | --- | --- |
| iPerf3 | `iperf3 --server --interval 0`, journald unit `iperf3` | Connection metadata and test summaries; interrupted tests may report nonsensical durations and rates |
| UDPST legacy | `udpst-legacy -v -p 24602`, journald unit `udpst-legacy` | Client address, sub-interval throughput/loss/delay variation, summary and peak capacity |
| UDPST modern | `udpst -K /etc/udpst/udpst.keys -G /var/lib/udpst/stats.json` | JSON schema 1.0 with periodic server-level statistics; per-client results not yet established |

Do not assume that modern UDPST server statistics identify individual customer tests. Do not treat an interrupted iPerf3 summary as a valid capacity measurement.

## Proposed architecture

1. **Read-only collectors** consume journald entries and a stable snapshot of the UDPST statistics JSON.
2. **Normalizer/validator** records protocol, direction, IP family, timestamps, metric units, completeness, and source provenance.
3. **Persistence** stores test summaries, test intervals, server statistics, and synchronization state separately. Preserve source-specific fields and avoid conflating server-wide counters with per-test measurements.
4. **Sync worker** uses persistent journald cursors, source record identifiers, and database uniqueness constraints to resume safely and avoid duplicate inserts.
5. **Optional authenticated API** requests an incremental synchronization and reads stored results. A sync request never initiates a network speed test.

## Proposed API (not implemented)

- `POST /api/v1/sync`: request an incremental import; return a sync job identifier.
- `GET /api/v1/sync/{id}`: job status, imported/skipped/invalid counts, and synchronization watermark.
- `GET /api/v1/results`: list authorized historical test results.
- `GET /api/v1/results/{id}`: retrieve one test and its intervals.
- `GET /api/v1/statistics`: query server-wide statistics.

Distinguish `last_measurement_at` (time of actual test) from `last_synced_at` (time import completed). A successful sync does not imply a new measurement exists.

## Reliability and security requirements

- Never modify, restart, or block existing test services.
- No inbound API exposure on the public speedtest interface by default; deploy API on a protected management endpoint if needed.
- Run collectors under a dedicated least-privilege account with read access only to necessary sources.
- Keep credentials outside Git; grant minimal database permissions.
- Use bounded ingestion batches, retry/backoff, safe atomic JSON reads, and transactional cursor commits.
- Handle log rotation, restarts, incomplete test sessions, duplicate entries, and malformed timestamps.
- Treat client IP addresses and raw logs as potentially personal data; apply access controls and retention limits.
- Limit and authenticate on-demand sync to prevent resource abuse.
- Keep firewall manager and prefix synchronization completely independent.

## Planned milestones

1. Capture representative **sanitized** logs/JSON fixtures and write parser tests, including incomplete iPerf3 sessions.
2. Build a read-only CLI importer with JSON output; no database dependency initially.
3. Select MariaDB or PostgreSQL and implement schema, idempotent persistence, and checkpoints.
4. Add periodic sync and a protected on-demand sync API.
5. Add query endpoints, operational metrics, and optional dashboard integration.

## Development

Use the `develop-v1` branch for design and development. The `main` branch remains the initial repository baseline until an implementation has been reviewed and tested.
