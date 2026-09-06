### Task 14 — Test installed broker identity and authorization boundaries

- Depends on: the implemented [installed runner](../../tests/integration/README.md).
- Complexity: very high. These are security boundaries that cannot be proven by
  same-UID mocks.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Model rationale for remaining work: real authentication and revalidation
  during approval still require security-sensitive fixture design and installed
  verification. The 213-case matrix and persistent caller role checks are accepted.
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
- Completion criteria: every method/role cell in the
  [broker interface matrix](../SystemDesign/Broker.md#broker-interface-and-roles) has an
  installed-system assertion and cross-account attempts fail closed.

## Continuation handoff — 2026-09-05 (incomplete)

Continue Task 14 only on this development host and the already-authorized
existing `ubuntu26.04` VM. Resume with **`gpt-6-astra` / `high`**; no repeat
machine clarification or model-selection pause is needed on that setting.
Remaining real authentication and in-flight revalidation require security-sensitive
fixture design. Task 14 remains unchecked.

### Remaining work

1. Add a real text authentication agent around the existing persistent caller.
   Prove successful child and kiosk approvals, restriction to the selected
   administrator, rejection of another administrator's credentials, and no
   reusable management authority after approval. Use public
   [pkttyagent](https://polkit.pages.freedesktop.org/polkit/pkttyagent.1.html)
   `--system-bus-name <caller.name>` and `--notify-fd`; successful registration
   closes the passed FD. PTY/password orchestration is not implemented.
   Keep distinct temporary fixture passwords in memory, pass password-setting
   input through stdin inside the guarded VM only, and keep credentials out of
   arguments, output, pytest diagnostics, and artifacts. Never install permissive
   test Polkit rules or inject approval. Pin directly spawned agents and run new
   cleanup-safety regressions in isolation before integrated use.
2. Hold approval at the real prompt, change accounts/roles/preferences or
   disconnect the recorded requester, then finish authentication and assert
   fail-closed results plus unchanged authoritative grant/app state for every
   other account. Ordinary role changes on persistent connections are now
   implemented separately; they do not prove revalidation after authentication.
   Include stale/deleted accounts and selected-approver revalidation.
3. Finish evidence-backed broker/account mappings in `tests/requirements.json`.
   Existing installed references remain `planned`; do not claim authentication,
   in-flight revalidation, or E2E obligations covered without matching evidence.
4. Run the complete expanded system suite, inspect redacted logs, run
   `make check` and `git diff --check`, then update the single Task 14 checklist entry and
   record its final result/evidence in this task document. Stop before Task 15A.

### Reuse these interfaces

- `tests/integration/system_caller.py`: batch calls still drop real/effective/
  saved credentials and verify bus-reported UID. New `PersistentCaller(uid)`
  is a context manager that exposes `name`, `call(method, signature, args)`,
  and separate `send(operation)` / `receive(timeout)`. Operations use the
  existing `kind=call`, `method`, `signature`, `args` JSON shape.
  The child publishes its actual unique name after UID verification and handles
  newline-framed operations on the same connection. EOF closes it; context
  cleanup has bounded waits and can signal only the directly spawned pidfd.
- `tests/system/test_authorization.py`: reuse `batch`, `call`,
  `account_property`, and `account_state`. State snapshots compare private
  preference bytes, `LimitType`, `DailyLimit`, `ActiveExtension`, and
  `AppFilter` without printing contents.
- `system_runner.PHASE_COUNTS['authorization'] == 213`. New coverage adds
  14 ineligible-approver cases across both request surfaces, exact icons for
  both administrators, and persistent caller administrator-demotion/child-
  promotion cases. Keep the expected count aligned with collection.
- Product baseline is commit `90b42070819001ad32479be89637383907b7b62d`.
  The identity-scoped usage-query repair is accepted; do not redo its diagnosis.
  This continuation changes tests/documentation only: activation `none`, no
  migration or development-host setup change, no new commit.

### Verification and evidence

- Isolated prerequisites:
  `/usr/bin/python3 -B -m pytest tests/unit/test_system_caller_cleanup_safety.py tests/unit/test_system_runner_cleanup_safety.py tests/unit/test_prepare_host_cleanup_safety.py -q`
  — 25 passed before the expanded VM run (the seven new caller cases also
  passed alone).
- Focused host checks:
  `/usr/bin/python3 -B -m pytest tests/unit/test_system_caller.py tests/unit/test_system_runner.py tests/unit/test_system_guest.py tests/unit/test_vm_transport.py -q`
  — 94 passed. Authorization collection confirms exactly 213 cases.
- Host cleanup prerequisite
  `/usr/bin/python3 -B -m pytest tests/unit/test_child_preview_cleanup_safety.py -q`
  — 11 passed, three subtests passed. `make check` passed 816 unit/contract and
  17 component tests; stage traceability validation passed.
- VM command:
  `pkexec make -C /Data/Code/PST/parent-control check-system ARTIFACT_DIR=/tmp/onpc-task14-resume-nhtsRC/input`.
  The corrected 195-case run passed all cases plus four install/reboot checks
  at `/tmp/onpc-system-u0c5ozv_/evidence/` (authorization 51.528s).
  Aggregate outcome passed, cleanup complete; VM independently confirmed off.
- Expanded run: **213 authorization cases passed** in 75.331s, plus four
  install/reboot checks, no failures/errors/skips. Evidence:
  `/tmp/onpc-system-61fofrz8/evidence/`, including aggregate JSON/xUnit/TAP,
  guest XML, and redacted broker/service logs. Aggregate outcome passed,
  category `all-checks-passed`, cleanup complete. Logs confirm each persistent
  caller's accepted/denied/accepted sequence around the role change.
- Cleanup verified the retained baseline, restored prior domain XML and checked
  unchanged host product/PAM fingerprints. A separate
  `virsh --connect qemu:///system domstate ubuntu26.04` confirmed `shut off`.
  No command remains running. `git diff --check` passed. This is the clean
  checkpoint after the user's ten-minute limit; resume by saying
  `Run docs/Test-Automation.md`.
- Verified package directory: `/tmp/onpc-task14-resume-nhtsRC/input/`.
  SHA-256: `bfdd5e4eef68d645c70e6792019c8f9cb1187f20d2619151c7f86ff2cd18cce0`.
  Each runner invocation freezes/transfers current test bytes. Rebuild only if
  product code changes; recheck temporary paths when resuming.
- Preserve earlier failed evidence at `/tmp/onpc-system-oo7urqih/evidence/`
  (194/195; corrected unsupported duration input), `/tmp/onpc-system-erwox8b2/evidence/`,
  and `/tmp/onpc-system-f35sqzni/evidence/`. A later successful corrected run
  does not relabel those attempts.
