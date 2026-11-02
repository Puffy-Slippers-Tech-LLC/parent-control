# 004 — Restore the extension after startup and reboot

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Category: system. Requires: 001. Estimate: 30–60 minutes.
Session exception: cold boot, offline settings and subsequent native activation
must remain one installed history per target with its original saved controls.

Read the [master reuse map](../Extension-Plan.md#reuse-and-duplicate-avoidance),
[broker readiness](../SystemDesign/Lifecycle.md#broker-readiness),
`Broker.refresh_enabled_extensions`, `Service._start_policy`, and the existing
system 281/282 helpers. These v1.5 entry points already exist; add only missing
assertions and the new monitor composition checks.

Cover a saved-enabled child with individual/global disablement across:

- Broker startup/restart in an existing desktop, checking actual configured/active
  state and exact other-extension choices.
- An offline child before login: verify durable settings recovery, then actual
  Shell activation after a normal fresh login.
- A real OS reboot with retained saved controls, then a usable native child
  session. Neither Parent nor kiosk approval supplies the missing startup repair.

Preserve saved-off controls, original grants and unrelated users. Reuse the
existing unavailable-home/child-local failure and shared-payload refusal owners;
do not create a second rollback or installation-failure matrix. Healthy startup
must not rewrite unrelated extension choices.

Existing selectors are system 281 (`enforcement::test_kiosk_expiry_installed_runtime`)
and 282 (`session::test_kiosk_expiry_graphical_runtime`). Discover their current
scoped bindings with `tools/run-tests system --list`; extend/extract only the
missing standalone startup delta without copying full natural-expiry histories.
Record the actual implemented selector, both target results and owned cleanup.
