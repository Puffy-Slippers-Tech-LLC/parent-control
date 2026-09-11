# 15A activation interface audit — 2026-09-11

Development-host slice, `gpt-6-astra/high`, Standard. All-task guarded VM
clearance persists. Task 20's evidenced source-change deferral was rechecked:
the release-tool additions remain present, with no new writer-completion or
arranged-window evidence. No unchanged stability experiment ran.

## Discriminating findings

The released upstream v1.4.5 interface was audited; this is **not an assertion
that the test guest has that version**. Public sources:

- [CLI manual](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.4.5/doc/fapolicyd-cli.8):
  reload notifies; listing reads rules on disk; status exposes performance data.
- [Policy implementation](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.4.5/src/library/policy.c):
  `open_file` hashes the opened file and emits its identity before parsing.
  `load_rule_file` only opens it; `do_reload_rules` destroys the prior rules and
  invokes `_load_rules` later. A matching journal digest therefore cannot prove
  successful activation or rollback. This rejects a concrete candidate witness,
  beyond the already-known notification-command limitation.
- [Status implementation](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.4.5/src/daemon/fapolicyd.c)
  `do_stat_report`, and
  [decision reporting](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.4.5/src/daemon/notify.c)
  `decision_report`, provide configuration/performance observations, not a
  requested generation's activation receipt.

The existing boot canary is fixed and only proves initial enforcement. A new
generation witness must discriminate stale rules and a stopped/permissive
daemon, as well as candidate activation. A denial alone can be unrelated access
failure; an allowance alone can be absent enforcement. Any proposed kernel
probe needs both controls, bounded owned execution, generation binding, and
rollback/removal semantics before adoption. No new probe protocol, journal
parser, private FIFO access or arbitrary delay was introduced.

## Missing identity evidence and implemented increment

The approved read-only artifact helper returned `FileNotFoundError` for
`/tmp/onpc-system-f3jqhqra/evidence/guest`. The host package query found no
fapolicyd installation. Historical narrative remains, but this session could
not independently reopen that guest evidence or identify its dependency
version. Do not substitute the audited upstream tag for the installed version.

`system_enforcement.record_execution_backend` now records the installed
fapolicyd Debian version and executable SHA-256 before policy access in each
native transition case. It reuses the guarded guest command runner, its private
diagnostics and JUnit property callback. The version query has a ten-second
timeout; bounded version validation precedes publication. Query/hash failure
cannot publish a partial identity. These properties identify installed files,
not the running daemon or active policy. No product behavior, integration
activation class, persistent schema, runner privilege or cleanup rule changed.

## Verification and remaining work

- Initial `tools/run-unit-tests tests/unit/test_system_enforcement.py -q`:
  **19 failed, 154 passed**. Retention/pattern cases restored real hashing and
  reached the absent host binary. The rig now maps the dependency binary to its
  owned fixture; real hashing of rule and target files remains exercised.
- Final `tools/run-unit-tests tests/unit/test_system_enforcement.py
  tests/unit/test_execution_policy.py tests/unit/test_execution_policy_ready.py
  -q --tb=short`: **191 passed, 8 subtests passed**. New checks cover valid
  Debian versions, malformed/private output rejection before policy access,
  command/hash failure without partial publication, and scenario integration.
- Changed links and scoped whitespace checks passed. No build, VM attempt,
  `make check`, installed qualification or checklist promotion. The two prior
  activation attempts retain their original outcomes.
- A guessed readiness-module path and two guessed system-module paths were
  absent; maintained paths were resolved from task references/file discovery.
  A guessed upstream policy source URL returned 404; the release tree resolved
  it to `src/library/policy.c`. No approval or Polkit denial occurred.
- Every command exited; no VM, lease, worker, screenshot or owned background
  process started. Tests used temporary fixtures; no recovery obligation remains.
  Existing unrelated edits and historical logs were preserved.

Next: settle a generation-specific kernel witness using the public rule/execute
interfaces, with stale/absent enforcement controls and rollback/removal failure
semantics. Validate it locally before a guarded native attempt. Capture the
actual installed version with the new helper on that attempt and audit its
matching supported interface. Full acknowledgement, route/update, Snap/Flatpak
and task acceptance remain open. Task 20 returns first when its documented
source-stability condition is established.
