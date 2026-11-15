# Eltern-Portal MCP Bavaria

A local [Model Context Protocol](https://modelcontextprotocol.io/) server for
school portals at `SCHOOL.eltern-portal.org`. Built from the portal experience and
HTML parsers in [Eltern Portal Manager Bavaria for Home Assistant](https://github.com/FabusMingAI/ha-schulmanager).

**42 tools · multiple schools and children · local tasks · persistent cache · no extra AI API key**

[![Tests](https://github.com/FabusMingAI/elternportal-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/FabusMingAI/elternportal-mcp/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Version **0.2.0 is a community preview**. The demo, MCP protocol and
fixture-based portal flows are tested automatically. This standalone server has
not yet been validated with a real school account. Availability and layouts vary
by school; MFA is not implemented. This is an unofficial project, unaffiliated
with art soft and more. It is for **Eltern-Portal**, not Schulmanager Online.

Deutsch: [Anleitung und Einrichtung](docs/DEUTSCH.md).

## What it does

| Area | Features |
|---|---|
| Family | Multiple schools; explicit child IDs prevent ambiguous lookups |
| Inbox | Letters, subject-teacher messages, bulletin board, polls; search and date filters |
| Lessons | Timetable, times, rooms, teachers; substitutions and cancellations parsed locally |
| Calendar | School events and exams; optional filtering for the child's class |
| Other portal data | Existing sick notes; class register/homework where enabled |
| Documents | Explicitly approved PDF downloads; local text extraction, pagination and search |
| Organization | Local tasks, EUR payment amounts, deadlines, comments and processing states |
| Reliability | SQLite persistence, per-section fetch status, retained stale data and cache age |
| MCP | 42 annotated tools, a usage resource and two review/briefing prompts |

No portal messages, sick notes, votes, bookings or payments are submitted. Local
task states do not change the school portal. Opt-in background polling, reminders and morning briefings are available; push/voice delivery uses explicitly configured Home Assistant services.

## Try it without an account

Requires **Python 3.13+**. The CLI uses stdio, so running it directly waits for an MCP client.

```bash
git clone https://github.com/FabusMingAI/elternportal-mcp.git
cd elternportal-mcp
python3.13 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install .
elternportal-mcp --demo
```

The demo uses synthetic, current data for two children and makes no portal
network requests. Its data directory is separate from the real configuration.
Set `ELTERNPORTAL_DEMO_DATA_DIR` to override it.

Generic MCP client configuration:

```json
{
  "mcpServers": {
    "elternportal": {
      "command": "/absolute/path/elternportal-mcp/.venv/bin/elternportal-mcp",
      "args": ["--demo"]
    }
  }
}
```

On Windows use the absolute path to `.venv\\Scripts\\elternportal-mcp.exe`.
Use your client's configuration mechanism for stdio servers; the JSON above is
the common `mcpServers` format. The repository includes a [TOML example](examples/mcp-client.toml).

Example questions: “What changed in Alex's lessons?”, “Which letters mention the
museum?”, “Show open local payment tasks.” Start with `list_children` and use
its exact IDs. The MCP client performs the natural-language analysis.

## Connect your schools

1. Copy [examples/config.example.json](examples/config.example.json) to a private
   location, for example `~/.config/elternportal-mcp/config.json`.
2. Set the school code, parent email and a **password environment-variable name**.
   Repeat entries for different schools. The password itself is never a tool argument.
3. Provide those environment variables to the MCP process, e.g. through your
   client's private server configuration. Do not commit credentials.
4. Replace `--demo` with `--config /absolute/path/config.json` in the client.

Example private configuration:

```json
{
  "schools": [
    {"school": "myschool", "username": "parent@example.invalid", "password_env": "SCHOOL_ONE_PASSWORD"},
    {"school": "otherschool", "username": "parent@example.invalid", "password_env": "SCHOOL_TWO_PASSWORD"}
  ],
  "cache_ttl_seconds": 900,
  "lookback_days": 120,
  "request_timeout_seconds": 30,
  "allow_pdf_downloads": false
}
```

Full HTTPS school URLs are accepted and normalized to school codes. Custom hosts
and plaintext HTTP are rejected. Do not use the operating system's `USER`
variable. Configuration discovery: `--config`, then `ELTERNPORTAL_CONFIG`, then
`~/.config/elternportal-mcp/config.json`.

Data is stored under `~/.local/share/elternportal-mcp` unless `data_dir` is set.
It includes personal school text and local tasks, unencrypted on your disk;
the database is created with owner-only permissions on POSIX. Back up or remove
this directory consciously. Windows access control follows the parent folder.

## PDF downloads can confirm receipt

**Downloading a parent letter can automatically confirm its receipt at school.**
This server therefore never downloads attachments during refreshes or inline-text
reads. To download a specific PDF:

1. Enable `allow_pdf_downloads` in your private configuration and restart the server.
2. Ask for that specific attachment and explicitly agree to the possible receipt confirmation.
3. The client calls `download_pdf` with `confirm_possible_receipt=true`.
4. Read the extracted text with `get_cached_document`, which makes **no network request**.

An extraction failure may happen after the portal has already recorded receipt.
The server does not silently retry downloads. Check the portal before retrying.
If receipt confirmation is unacceptable, leave downloads disabled and open the
document manually in the portal. Existing cached text can still be read.

Attachments are limited to 25 MiB. Explicit downloads preserve original files per child/school year unless `store_original_attachments=false`; PDFs are parsed in a time-limited subprocess. Up to 50 pages / 200,000 characters are extracted; truncation is reported.
Scanned/image-only PDFs are marked `ocr_required`; OCR is not included.
On POSIX the worker additionally uses CPU and memory limits; Windows uses the
subprocess timeout and input/output bounds. This is not an operating-system sandbox.

## Organization, analysis and HA parity

Version 0.2 adds automatic portal tasks, evidence-backed analysis, translations, local read/unread state, inbox/event archive, snoozing, a unified calendar with ICS export, daily lesson overlays, statistics, a family overview, change alerts and original attachments. See the complete [HA feature comparison](docs/HA_PARITY.md) and [optional bridge / background setup](docs/HA_BRIDGE.md).

The original tools below remain available. Additional tools are documented in the comparison.

## Tools

| Tools | Purpose |
|---|---|
| `get_health`, `list_schools` | Local diagnostics and configuration; no login |
| `list_children`, `refresh_school`, `get_capabilities` | Children, explicit refresh and per-area fetch status |
| `list_items`, `get_item` | Search/paginate inbox; read inline text without PDFs |
| `get_timetable`, `get_substitutions` | Timetables and changes; no external model needed |
| `get_appointments`, `get_sick_notes`, `get_class_register`, `get_teachers` | Calendar and additional data |
| `download_pdf`, `get_cached_document` | Explicit download versus local text read |
| `set_item_status` | Local processing state/comment, separate from portal receipt |
| `list_tasks`, `add_task`, `update_task`, `get_overview` | Local task/payment organization and compact briefing |

List tools return at most 100 records per page. Text tools return at most 30,000
characters per call. Payment amounts use integer cents and EUR; they are local
task values, not accounting data fetched from school. Use `clear_due` or
`clear_amount` to remove those fields from a task.

## Freshness and limitations

- Fetches are serialized per school; every refresh uses a fresh HTTPS session.
  Child selection and subsequent requests stay together. TLS verification is enabled.
- The default cache is 15 minutes. Refresh attempts are limited to once a minute
  per school per process. Request timeout defaults to 30 seconds; a whole refresh
  is limited to five minutes. Background polling is opt-in; use `background_enabled=true` and keep the MCP process running, or run `elternportal-mcp --config /path/config.json --worker`.
- A failed full refresh preserves the prior snapshot and marks it stale. Failed
  individual sections retain prior data with `status=unavailable`, `retained=true`
  and their previous `fetched_at`. Always inspect both source and section status.
- `status=ok` means the last fetch/parse succeeded; it is not proof that every
  feature of a school's portal is supported. Some HTML differences remain possible.
- A successful empty section replaces prior records. Inbox items remain locally searchable after leaving the current snapshot. Read/status/archive state, analyses and local tasks persist; a bounded change log records edits.
- Class-register/homework uses a window from today through four days ahead and
  especially needs real-school testing. No class-teacher messaging or student-portal support.
- MFA, document libraries, booking, voting, leave applications and other portal
  writes are not implemented. Supported read areas vary with school permissions.
- The portal has no documented public API used by this project. Its web pages and
  internal endpoints may change. Use only your authorized account.
- Local rules require no AI provider. Explicit model analysis uses client sampling or the optional HA AI Task provider; opt-in automatic HA analysis can do so in the background. Your MCP client may send returned
  school data to its configured model provider. Treat all portal content as
  untrusted data; tool annotations are hints and do not replace client consent.

## Development

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
pytest --cov=elternportal_mcp --cov-report=term-missing
python -m build
```

Tests include real stdio MCP calls, subprocess restart persistence, synthetic
portal HTTP flows, child switching, parser layouts, expired login handling,
download gates, PDF extraction and outage retention. They require no real
credentials. See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and
[ROADMAP.md](ROADMAP.md).

## Attribution

MIT. Portal parser adaptations come from
[FabusMingAI/ha-schulmanager](https://github.com/FabusMingAI/ha-schulmanager)
(MIT); the underlying [pyelternportal](https://github.com/michull/pyelternportal)
library is Unlicense. Details in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
