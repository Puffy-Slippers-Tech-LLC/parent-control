# 015 — Prepare agent readiness through setup and SSH

Acceptance: host

Purpose: remove shared setup/remote admission dependence on a hardcoded provider.
Requires task 014. This task has no paid Claude or SDK prerequisite and grants
no native Claude policy preparation or execution capability.

Read the [master](../Agent_Adapter.md),
[setup boundary](../Agent-Adapter-Design.md#permissions-instructions-and-setup),
[remote requirements](../Agent-Adapter-Design.md#remote-execution-watch-and-failure-handling)
and [setup authority](../Approval-Tools.md#one-time-setup). Inspect affected complete
functions in `setup.sh`, `tools/setup_checkout.sh`, `tools/install_codex_rules.py`,
`tools/launcher_controller.py` and their discovered shared consumers/regressions.

Keep `./setup.sh` as the only development setup entry point. Route readiness
through the fixed selected-agent boundary, preserving existing Codex preparation
and personal settings, trust and authentication. A known unqualified provider
receives an actionable readiness message, not an installation/authentication
attempt, native Claude model request, fallback or widened privileged authority.

For SSH, resolve the executing checkout and account before selected CLI readiness.
Replace shared hardcoded Codex startup assumptions with the maintained native
environment capability boundary while preserving needed Codex/Node discovery.
Do not source arbitrary interactive rc files, forward client credentials, add
provider options or require CLI readiness for stop/observation/help. Keep branch
dispatch, destination identity and host ownership checks unchanged.

Validation: existing focused setup/controller/dispatch checks cover selected
checkout identity, supported Codex startup, absent/unqualified provider errors,
and agent-free operations. Use a bounded registered remote check only when
affected remote behavior requires it and existing authorization permits it;
otherwise report the exact validation limit. No product or CLI installation,
Claude SDK, live Claude session or VM operation is necessary for shared plumbing.
The session exception covers the coupled local/remote admission boundary.

Adapt existing core regressions only; add no non-product tests. Finish owned
cleanup, check Markdown links and run `tools/build_package.py` after any final
build-affecting edit. Leave native Claude host/skill qualification to task 008.
