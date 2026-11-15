# Changelog

## 0.2.0 — 2026-11-15

Adds 22 tools for HA feature parity: automatic receipt/poll tasks, evidence-backed
analysis, multilingual summaries, read/unread state, archive, snooze, unified
calendar/ICS export, daily plan, family statistics, original attachments and
change alerts. The optional HA bridge provides AI Task, WebUntis calendars,
push, voice and mobile done/snooze actions. Background operation is opt-in in the
MCP process or standalone `--worker`, with a shared worker lease and retryable,
per-target-deduplicated delivery. Existing v0.1 SQLite state migrates in place.

UI-specific HA dashboard cards/entities remain in the HA integration. No portal
write actions are added. See docs/HA_PARITY.md and docs/HA_BRIDGE.md. Real-service
validation is still outstanding; automated tests use synthetic data/mocks.

## 0.1.0 — 2026-11-15

Initial community release with 20 MCP tools, an offline synthetic demo,
multiple-school/child support, locally parsed timetables and substitutions,
inbox/calendar reads, existing sick notes and class-register access, local
tasks/payment amounts, SQLite persistence and stale-section retention.

PDF text extraction is separate from inline reads: downloads are disabled by
default and explicitly acknowledge possible school receipt confirmation.

Includes stdio protocol and synthetic portal-flow tests, GitHub Actions,
English/German setup documentation and upstream parser attribution.
Real-school validation of this standalone MCP server is still outstanding.
