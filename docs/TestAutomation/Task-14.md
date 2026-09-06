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

Task 14 remains unchecked. Continue this task only. The user confirmed this
checkout is on the development host and authorized the existing `ubuntu26.04`
VM. No further machine clarification is needed.

Recommended continuation: **`gpt-6-astra` / `high`**. Remaining work includes
real authentication, stale identities, caller lifetime boundaries, and installed
acceptance of the usage-query repair.

### Reuse these implemented interfaces

- `tests/integration/system_caller.py`: guarded JSON batch caller; drops real,
  effective, saved UID/GID and supplementary groups before opening a fresh
  system-bus connection; verifies the bus-reported UID. Returns public error
  names and never private preference contents.
- `tests/system/test_authorization.py`: `batch(uid, operations)` and
  `call(uid, method, signature, args)` use identity-recorded
  `owned_commands.Commands`. Current suite: 142 cases (17 methods × seven
  roles, 15 cross-child attempts, seven file/log cases, discovery).
- `system_runner.PHASE_COUNTS['authorization'] == 142`; new cases must update
  this count and its tests. The guarded runner freezes/hashes all test inputs,
  executes install/reboot/authorization phases, and rejects incomplete evidence.
- Account setup now captures four read-only Malcontent `QueryUsage` probes in
  order: root, parent1, child1, kiosk. Raw responses stay in private diagnostics
  and redacted collected copies; probes do not relax the product assertions.

### Confirmed defect and local repair

The diagnostic VM run reproduced all seven `GetTimeStatus` failures on the
unchanged package: 135 passed, seven failed, zero errors/skips. The dependency
probes proved root is rejected as an invalid/unknown user, parent and child
self-reads return `a(tt) 0`, and kiosk's cross-account read is denied.

This matches the public upstream
[Malcontent implementation](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/parent-timer-service.c):
`query_usage_ensure_credentials_cb` rejects UID 0;
`query_usage_get_child_user_cb` permits parent or self reads. The current
`main` source was also checked and retains these boundaries.

Local repair is implemented, but **has not been built or tested in the VM**:

- `TimerUsage.query_usage(uid)` now runs the existing fixed-purpose helper
  as the exact selected child's UID/primary GID, with no supplementary groups.
  The broker's caller/target authorization remains before this read.
- `query_usage_as(uid, approver)` retains authenticated-approver identity
  validation. Both paths share bounded helper execution and reply validation.
- `Broker._time_status` logs a fixed failure stage and exception type without
  raw exceptions or account data. Adapter logs distinguish own/approver scope.
- Adapter regressions prove selected-child credentials, absence of root-bus
  queries, redacted logs, and refusal to launch for a missing child.
- `docs/System-Design.md` describes the path. Activation is
  `process-restart` through existing broker classification; no saved-data
  migration or development-machine setup change applies.

### Remaining work, in order

1. Build a fresh package with `make build-test-artifacts OUTPUT_DIR=<fresh-/tmp-path>`;
   the previous artifact below does **not** contain the repair. Run the guarded
   authorization matrix and require all existing success cells to pass.
   Preserve both historical failed runs; do not relabel a backend error as success.
2. Add installed assertions for enabled-child `RequestOwnAccess`, ineligible
   system/noninteractive callers and targets, exact authoritative icons, and
   state isolation for other accounts. Disabled-child and agentless kiosk
   denial alone do not prove successful request admission.
3. Add persistent real-caller connections and controlled real authentication
   for stale-account, changed-role, selected-approver revalidation, and caller
   disappearance during approval. Use actual credential verification and public
   interfaces; never add permissive test Polkit rules or inject approval.
   [pkttyagent](https://polkit.pages.freedesktop.org/polkit/pkttyagent.1.html)
   supports `--system-bus-name` and `--notify-fd`; PTY/password orchestration
   is not implemented. Keep credentials in memory, out of arguments/logs.
   Add and separately run caller/agent cleanup-safety regressions before these
   integrated tests; signal only directly spawned, identity-pinned processes.
4. Update broker/account traceability only as supported by executed evidence.
   The manifest remains unchanged. Run stage validation after mapping changes.
5. Complete `make check-system`, inspect redacted logs/results, run
   `make check` and `git diff --check`, then update both Task 14 checkboxes
   and append its completion record. No later task is authorized in this run.

### Latest verification and evidence

- Before VM execution:
  `/usr/bin/python3 -B -m pytest tests/unit/test_system_runner_cleanup_safety.py tests/unit/test_prepare_host_cleanup_safety.py -q`
  — 18 passed in isolation.
- Before host checks:
  `/usr/bin/python3 -B -m pytest tests/unit/test_child_preview_cleanup_safety.py -q`
  — 11 passed, three subtests passed.
- Runner/caller regressions:
  `/usr/bin/python3 -B -m pytest tests/unit/test_system_caller.py tests/unit/test_system_runner.py tests/unit/test_system_guest.py tests/unit/test_vm_transport.py -q`
  — 86 passed.
- Post-repair:
  `env PYTHONPATH=broker /usr/bin/python3 -B -m pytest tests/unit/test_adapters.py tests/unit/test_core.py -q`
  — 88 passed, 17 subtests passed. An initial invocation without `PYTHONPATH`
  failed collection only; use the exact command above.
- Post-repair `make check`: 801 host tests and 17 component tests passed;
  `git diff --check` passed.
- Diagnostic command:
  `pkexec make -C /Data/Code/PST/parent-control check-system ARTIFACT_DIR=/tmp/onpc-task14-DLDL6r/input`
  — Make exit 2, aggregate `outcome=failed`,
  `category=command:failed:ssh`, `cleanup_phase=complete`.
  Install and reboot each passed two cases; authorization ran 142 cases in
  36.636 seconds, with the seven known `GetTimeStatus` failures.
- Latest evidence: `/tmp/onpc-system-f35sqzni/evidence/`.
  Under `guest/`, the four dependency probes are
  `stage-j8pk1y0m-command-0006-stderr.txt` (root),
  `0007.txt` (parent), `0008.txt` (child), and
  `0009-stderr.txt` (kiosk), using that same filename prefix.
  Broker logs and all three xUnit files are preserved there.
- First failed run remains at `/tmp/onpc-system-erwox8b2/evidence/`.
  Both attempts used package SHA-256
  `8eb84c03f463ab4ea79529104571ea83e38fb7f1e2f9e9c3185d7bc444560fb4`.
  Baseline provenance SHA-256:
  `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.
  Recheck temporary artifact existence next session.
- Cleanup restored and verified the retained baseline and host fingerprints.
  A separate `virsh --connect qemu:///system domstate ubuntu26.04` confirmed
  `shut off`. No commands remain running. The local repair is uncommitted.
- Paused at the user's ten-minute clean checkpoint after VM cleanup and local
  checks. Resume by saying `Run docs/Test-Automation.md`.
