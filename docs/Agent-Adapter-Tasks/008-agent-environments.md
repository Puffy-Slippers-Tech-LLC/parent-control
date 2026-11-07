# 008 — Complete Claude host and skill integration

Acceptance: host

Purpose: complete and qualify Claude-native environment and skill support
through the shared boundary, without a new launcher. Requires tasks 007 and
016 and explicit reactivation; production Claude execution stays disabled.
Reuse accepted setup/SSH/Watch infrastructure from tasks 015–016; do not repeat
its implementation or Codex qualification solely to refresh evidence.

Read the [master](../Agent_Adapter.md),
[setup requirements](../Agent-Adapter-Design.md#permissions-instructions-and-setup),
[remote/Watch requirements](../Agent-Adapter-Design.md#remote-execution-watch-and-failure-handling),
[integration map](../Agent-Adapter-Design.md#current-integration-map) and
[setup authority](../Approval-Tools.md#one-time-setup). Discover relevant setup,
controller, Watch, skill, source-archive and reload assets from the map before
reading their complete affected functions and consumers.

Keep `./setup.sh` as the sole development setup entry point. Add native policy
preparation and readiness reporting while preserving personal settings, trust,
authentication and inactive-agent files. Do not install or authenticate coding
CLIs during tests or preflight, or repurpose privileged Codex-rule authority.
Keep credentials, personal paths, history and local permissions out of Git.

Replace Codex-specific remote readiness assumptions with executing-checkout and
account selection; do not source arbitrary shell startup files or transfer
client credentials. Keep observation/stop independent of CLI readiness. Include
actual agent/model/effort in Watch/session metadata without changing public
start/resume/reload commands. Prepare supported instruction/skill discovery and
fresh-session defaults. Update controller reload and response-validator source
inventories and preserve product/source-archive exclusions.

Acceptance requires bounded local and configured remote readiness/dispatch
checks, meaningful missing-capability errors, reload-boundary behavior and
agent-free observation/help. Apply existing UI and VM mandates only if the
chosen checks actually operate those surfaces; no Watch-widget tests or product
installation is needed for transport readiness. The session exception covers
the coherent environment handoff across entry points; split independent changes
before execution if necessary.

Use established grants and existing checks, with no new non-product tests.
Complete owned cleanup and Markdown links. Run `tools/build_package.py` after
the final edit that can affect packaging; retain unresolved prerequisites rather
than installing them automatically.
