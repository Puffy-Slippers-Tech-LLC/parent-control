# 013 — Validate the configured agent

Acceptance: host

Purpose: prepare strict configuration and a fixed immutable selection boundary.
Requires task 003. This task needs no Claude subscription, authentication, SDK
or native request, and does not enable Claude execution.

Read the [master](../Agent_Adapter.md),
[selection requirements](../Agent-Adapter-Design.md#reading-and-changing-the-selection),
[adapter boundary](../Agent-Adapter-Design.md#adapter-boundary) and
[approval contract](../Approval-Tools.md). Inspect complete relevant functions
in `tests/integration/vm_config.py`, `tools/vm_selection.py` and
`tools/agent_adapter.py`; discover their existing regressions before reading.

Keep one shared document parser and preserve duplicate-key/structural checks.
When present, validate `agent` as exactly `codex` or `claude`; legacy agent-free
documents may omit it. Prepare a live-session selection API that requires the
field and records its executing checkout. Use an immutable snapshot and fixed
adapter/capability mapping, never an arbitrary import or executable from config.
Do not read provider choice from CLI options, environment or retained provenance.

Preserve the existing Codex runtime path until the caller handoff in task 014 is
coherent. Parsing the string `claude` grants no readiness or execution capability;
an attempt to use the unqualified adapter must fail clearly before spawning it,
without fallback or installing prerequisites. Keep Claude imports/SDK optional.

Validation: use existing focused parser/selection regressions for valid values,
missing legacy/live values, invalid types/values, duplicate keys and unreadable
configuration. Check agent-free help/listing needs no CLI or model access. No
new non-product tests are authorized; adapt existing critical guard coverage.
Use the lowest effective maintained test selection, preserve Codex acceptance
and run Markdown link checks. Finish owned cleanup and record only new scoped
results; no renewed historical proof or product installation is needed.
