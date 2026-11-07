# 016 — Show agent provenance and track adapter assets

Acceptance: host

Purpose: finish shared observation and asset integration without live Claude.
Requires task 015. Preserve current Codex instructions/skills; native Claude
skill and policy qualification remains deferred to task 008.

Read the [master](../Agent_Adapter.md),
[remote/Watch requirements](../Agent-Adapter-Design.md#remote-execution-watch-and-failure-handling),
[integration map](../Agent-Adapter-Design.md#current-integration-map),
[reload boundary](../Execution-Plans.md#common-launcher-interface) and
[approval contract](../Approval-Tools.md). Inspect complete affected Watch/session,
usage, reload/source inventory and packaging consumers after source discovery.
Known entry points include `vscode/onpc-watch/extension.js`,
`tools/detached_launcher.py` and `tools/plan_launcher.py`.

Display recorded actual agent with native model/effort in existing session/Watch
surfaces. Preserve legacy unknown provenance, bounded transcript behavior,
read-only observation, task metadata and stop/resume/reload commands. Reuse the
shared readiness/environment route from task 015 for Watch startup rather than
duplicating Codex-specific SSH PATH checks or adding a provider picker.

Review controller reload and response-validator dependency inventories for shared
and optional adapter/bridge assets, including `plan_launcher.RESPONSE_VALIDATOR_SOURCES`.
Keep optional native dependencies lazy, credentials/private state ignored and
development adapter assets outside product payload/runtime/source-archive maps.
Do not install Claude, add native Claude skills/policy or claim its support.

Validation: existing focused observation/metadata/reload checks preserve Codex
and legacy records, actual-agent rendering, stable reattachment and owned reload
boundaries. Inspect the final asset/package maps. No Watch-widget tests or new
non-product tests are allowed; no live Claude request is required. The session
exception covers startup, presentation and reload consumers of one identity.

Finish owned cleanup and Markdown link checks; run `tools/build_package.py` after
the final edit that can affect build/packaging. Close only this task, preserving
deferred rows and setting the master pointer to `none` when active work is done.
