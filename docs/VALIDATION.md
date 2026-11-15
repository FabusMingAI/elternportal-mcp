# Release validation

## 0.2.0 — HA feature parity

Date: 2026-11-15. Local platform: Linux aarch64, Python 3.13.5.

- 76 automated tests passed, including 42-tool stdio discovery.
- Statement coverage: 86%, including MCP and PDF subprocesses.
- Real MCP sampling-callback test covers analysis and summary translation.
- Additional tests cover automatic receipt/poll tasks, read/unread changes,
  whitespace-stable fingerprints, source-quote validation, preservation of user
  edits, retained archive contents, preview versus accepted calendar events,
  ICS dates/times, reminder snoozes, unique sick weekdays and v0.1 database migration.
- Simulated integration tests cover HA AI/calendar routes, partial push retries,
  daily deduplication, done/snooze actions, WebSocket authentication, redirect
  rejection, WebUntis deduplication and stale-source retention.
- Background tests cover opt-in behavior, independent school failures, shared
  worker leases, cancellation cleanup and six-hour analysis/translation retries.
- Original-attachment tests verify child-scoped private file storage without
  executing or opening the downloaded file.
- The inherited course-evidence regression tests also run against the adapted
  HA timetable helpers.

All service responses and model outputs in these tests are synthetic. No real
portal credentials, HA token, notification recipient or speaker was used. Actual
school, HA AI, WebUntis and phone/voice compatibility still needs authorized
real-service validation. The GitHub Actions results provide the separate
Linux/Windows and Python 3.13/3.14 checks.

## 0.1.0 — initial release

Date: 2026-11-15. Local platform: Linux aarch64, Python 3.13.5.

- 43 automated tests passed.
- Statement coverage: 85%, including MCP server and PDF worker subprocesses.
- Ruff lint and formatting checks passed.
- Wheel and source distribution built successfully using an isolated build.
- Wheel includes parser attribution and both required license-notice files.
- Clean second environment: wheel installation, version command, actual MCP
  initialization, 20 discovered tools and two returned demo children passed.
- Test data is synthetic; no real account was used.

The protocol integration test starts an actual stdio MCP client/server pair,
discovers all 20 tools, calls each tool (including expected download refusal),
reads the guide resource, obtains a prompt and restarts the server to verify
task persistence. It also validates structured tool outputs and parameter bounds.

The simulated online flow exercises the real login/child-selection/parser
pipeline using pyelternportal's demo HTML plus a synthetic second child.
Transport tests cover authentication redirects, cross-origin redirect blocking,
request failures and streamed response limits. Additional tests cover partial
failure retention, cache restart behavior, task storage, PDF gates and extraction.

The pinned upstream pyelternportal version emits BeautifulSoup deprecation
warnings in its class-register parser. They did not fail the tests; the upstream
parser should be modernized in a future update.

This does **not** establish compatibility with every school or replace a
real-account comparison. MFA, class-register layouts and PDF receipt behavior
need authorized real-school validation. See ROADMAP.md.

The GitHub Actions matrix separately checks Linux/Windows and Python 3.13/3.14;
consult the actual workflow results for those platforms.
