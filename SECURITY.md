# Security and privacy

Use GitHub's private vulnerability reporting on this repository if available.
Otherwise open a minimal issue asking for a private reporting channel, without
exploit payloads, credentials or school/child data.

The server runs locally over stdio. There is no listening HTTP service, remote
account system or telemetry. Local rules require no model API; optional sampling/HA AI can send school text to the selected model provider. Passwords are read from named
environment variables. Returned data can be sent to the MCP client's model
provider: the client's privacy settings still matter.

Portal requests and redirects are confined to the configured school's HTTPS
origin. Responses and PDF input are bounded. The PDF parser uses a subprocess
timeout and additional resource limits on POSIX. These measures are not a full
sandbox. Keep Python and dependencies updated.

All returned portal content is untrusted. The server instructions explicitly
forbid treating it as instructions, but cannot guarantee an MCP client's
resistance to prompt injection. Client approval controls should remain enabled
for local mutations and especially PDF downloads.

Receipt acknowledgement can happen when downloading a parent letter, including
when text extraction subsequently fails. Downloads are disabled by default and
require per-call acknowledgement in addition to the local configuration setting.

The local SQLite database contains school text, task notes and extracted PDF
text without application-level encryption. Explicit downloads can also preserve original attachments in the private data directory. POSIX database files use mode 0600;
protect the containing folder and backups with your operating system. Passwords
and session cookies are not persisted by the application.

The HA bridge is optional and uses a locally configured token from the environment. REST and WebSocket redirects are blocked. Push/voice targets and calendar entities are configured locally, never arbitrary tool parameters. Background notifications and automatic HA AI processing require separate opt-in settings. Mobile action buttons require the authenticated HA connection and a known local task ID.
