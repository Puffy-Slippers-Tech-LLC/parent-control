### Task 14 — Test installed broker identity and authorization boundaries

- Depends on: Task 13B.
- Complexity: very high. These are security boundaries that cannot be proven by
  same-UID mocks.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Model rationale: keep the complete method/role matrix with stale-identity and
  real-caller checks; separating inexpensive cells would fragment the security
  argument and repeat sensitive fixture setup.
- Objective: prove real caller identity and role enforcement on the installed
  system bus.
- Work:
  1. In the guarded existing `ubuntu26.04` VM only, expand deterministic accounts to two eligible
     children, two eligible administrators, one locked administrator, the kiosk
     user, an unrelated standard user, and noninteractive/system fixtures.
  2. Invoke every broker method from real processes running under each relevant
     UID and record the allowed or denied D-Bus result.
  3. Verify account discovery after installation, sorting, exclusions, icon
     handling, locked-approver exclusion, and child-owned target derivation.
  4. Verify that front ends cannot read private preference records and cannot
     claim another component in `LogEvent`.
  5. Verify stale-account, changed-role, caller-disconnect, and selected-approver
     revalidation with actual system-bus names.
  6. Exercise interactive Polkit selection later through E2E; this task proves
     all non-graphical policy and broker boundaries.
  7. Update broker and account requirement mappings.
- Verification:
  - Run caller-process cleanup-safety regressions in isolation before integrated
    caller-disconnect tests.
  - Run the authorization matrix after restoring the retained baseline and
    installing the exact package in the existing VM; create no overlay.
  - Inspect redacted broker logs and D-Bus results.
  - Run `make check-system ARTIFACT_DIR=<verified-artifact-directory>`, `make check`, and
    `git diff --check`.
- Completion criteria: every method/role cell in `System-Design.md` has an
  installed-system assertion and cross-account attempts fail closed.

## Continuation handoff — 2026-09-05 (incomplete)

Task 14 remains unchecked. Continue this task only; no completion record is
appropriate until the remaining deliverables and installed assertions pass.
The user confirmed this checkout is on the development host and authorized use
of the existing `ubuntu26.04` VM. No further machine clarification is needed.

Recommended continuation: **`gpt-6-astra` / `high`**. The remaining work includes
real authentication timing, stale identities, and caller lifetime security
boundaries. It is not a lower-complexity acceptance-only continuation.

### Implemented interface to reuse

- `tests/integration/system_caller.py`: root entry checks `system_guest.guard`,
  consumes a JSON batch from stdin, initializes the selected account's groups,
  drops real/effective/saved GID and UID, clears inherited environment, and
  opens a fresh connection to `/run/dbus/system_bus_socket`. The bus-reported
  UID must match. The helper loads no product modules and returns public D-Bus
  error names, not exception messages. Its private-read operation opens only
  the exact selected preference record and never returns record contents.
- `tests/system/test_authorization.py`: `batch(uid, operations)` / `call(uid,
  method, signature, args)` reuse identity-recorded `owned_commands.Commands`.
  Module setup requires the VM guard before creating fixture accounts and
  applying empty application policies through the installed broker. The suite
  currently collects 142 cases: 17 methods across seven roles, 15 cross-child
  attempts, seven private-file/component-log cases, and discovery checks.
- `system_runner.PHASE_COUNTS` adds `authorization: 142`. The runner freezes
  and hashes the helper and suite, executes that phase after the existing
  install/reboot assertions, and rejects missing/failed/skipped evidence.
  Future additions must update the expected count and its verification.
- No production code or saved-data schema changed. Test-only activation is
  `none`. The integration README documents the unfinished phase.

### Remaining implementation and acceptance

1. Diagnose the seven `GetTimeStatus` failures from the first VM attempt below.
   Each of the seven allowed roles receives the public `BackendFailure` error;
   the other 135 cases pass. Broker logs confirm the error category but do not
   identify the underlying adapter exception. Inspect the installed usage-query
   boundary (`TimerUsage.query_usage` / `Broker._time_status`) and capture
   redacted dependency evidence in the next guarded run before choosing a fix.
   Do not replace expected success with acceptance of a backend error. Preserve
   failed evidence; a rerun does not erase a prior failure.
2. Extend the installed assertions for enabled-child `RequestOwnAccess`,
   ineligible system/noninteractive callers and targets, exact authoritative
   icon values, and state isolation for other accounts. Current disabled-child
   denial and agentless kiosk denial do not prove successful request admission.
3. Add persistent real-caller connections and controlled real authentication
   to prove stale-account, changed-role, selected-approver revalidation, and
   caller disappearance during approval. Use public interfaces with actual
   credential verification; never add permissive test Polkit rules or inject
   an approved result. An available supported starting point is
   [pkttyagent](https://polkit.pages.freedesktop.org/polkit/pkttyagent.1.html):
   `--system-bus-name` selects the actual caller, and `--notify-fd` reports agent
   registration. Its password-prompt/PTY orchestration has not been implemented.
   Keep fixture credentials in memory and out of command arguments and logs.
   Add caller/agent cleanup-safety regressions and run them in isolation before
   integrated disconnect tests; signal only directly spawned, pinned processes.
4. Add broker/account traceability mappings only as supported by executed
   evidence. The manifest is unchanged so far; do not claim planned races as
   covered. Run stage traceability validation after mapping changes.
5. Run the completed authorization suite via the guarded runner, inspect
   redacted logs and D-Bus evidence, run `make check` and `git diff --check`,
   update both Task 14 checkboxes and append its master completion record only
   after full acceptance.

### Checkpoint verification and artifacts

- Isolated prerequisite: `/usr/bin/python3 -B -m pytest tests/unit/test_system_runner_cleanup_safety.py tests/unit/test_prepare_host_cleanup_safety.py -q`
  — 18 passed.
- Focused: `/usr/bin/python3 -B -m pytest tests/unit/test_system_caller.py tests/unit/test_system_runner.py tests/unit/test_system_guest.py tests/unit/test_vm_transport.py -q`
  — 86 passed.
- Collection only (no VM actions): `env PYTHONPATH=tests/integration PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /usr/bin/python3 -B -m pytest -c tests/system/pytest.ini --noconftest --collect-only tests/system/test_authorization.py -q`
  — 142 collected.
- `make check` — 800 host tests and 17 component tests passed.
- `make build-test-artifacts OUTPUT_DIR=/tmp/onpc-task14-DLDL6r/input` — passed.
  This fresh artifact replaces the prior Task 13B `/tmp` input, which no longer
  exists. Do not assume temporary artifacts survive a new session.
- Live command: `pkexec make -C /Data/Code/PST/parent-control check-system ARTIFACT_DIR=/tmp/onpc-task14-DLDL6r/input`.
  Result: failed, exit 2 from Make (`command:failed:ssh` is the controller's
  wrapper category). Install and reboot each passed two tests. Authorization
  ran all 142 tests in 36.666 seconds: 135 passed, seven failed, no errors or
  skips. All failures are `test_method_role_matrix[GetTimeStatus-<role>]`.
- Preserved evidence: `/tmp/onpc-system-erwox8b2/evidence/` contains aggregate
  `result.json`, three guest xUnit files, redacted broker/component logs,
  service journal and structured caller replies. Aggregate `outcome=failed`,
  `cleanup_phase=complete`; the runner verified the restored baseline. A
  separate `virsh --connect qemu:///system domstate ubuntu26.04` returned
  `shut off`. No command is still running and no fixture account persists
  beyond the restored snapshot.
- Exact package SHA-256:
  `8eb84c03f463ab4ea79529104571ea83e38fb7f1e2f9e9c3185d7bc444560fb4`;
  baseline provenance SHA-256:
  `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.
- Pause: the run exceeded ten minutes; the first clean checkpoint was after
  the active VM runner completed cleanup. No additional implementation or
  whole-run retry was started. Changes are uncommitted.
