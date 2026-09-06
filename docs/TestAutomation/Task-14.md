### Task 14 — Test installed broker identity and authorization boundaries

- Depends on: the implemented [installed runner](../../tests/integration/README.md).
- Complexity: very high. These are security boundaries that cannot be proven by
  same-UID mocks.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Model rationale for remaining work: diagnose real PAM/Polkit denial using the corrected journal collector,
  then finish installed in-flight revalidation and disconnect coverage.
  All eight expected-success authentication cases currently fail.
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

Checkpoint: 2026-09-05 America/Los_Angeles (2026-09-06 UTC).
Continue Task 14 on this development host and the existing guarded
`ubuntu26.04` VM. **Recommended model: `gpt-6-astra`; effort: `high`.**
The user already confirmed this setting and machine; no repeat clarification
is needed. Real authentication diagnosis and the remaining security-boundary
coverage still warrant this setting. Task 14 remains unchecked.

### Remaining work, in order

1. Diagnose the expected-valid fixture password rejection. All eight real
   authentication cases now fail promptly with `agent:unexpected-denied`:
   six in-flight mutations and two selected-parent success cases. Agent
   registration, selected-identity prompts and wrong-password denial work.
   Do not revisit obsolete registration or timeout theories. The root cause
   of the actual authentication denial is **not established**.
2. Use the corrected authentication journal collection on the next guarded
   attempt. The latest attempt's `authentication-journal.txt` is empty because
   `journalctl -u polkit.service + SYSLOG_IDENTIFIER=polkit-agent-helper-1`
   is invalid (`"+" can only be used between terms`). After that attempt,
   `system_guest.collect` was corrected to explicit journal match terms:
   `_SYSTEMD_UNIT=polkit.service + SYSLOG_IDENTIFIER=polkit-agent-helper-1`.
   Its exit status is now checked. The corrected syntax passed a local
   read-only `journalctl ... -n 0` check, **but has not run in the VM**.
   Preserve the original failed evidence. Inspect the new redacted journal
   and, if necessary, collect safe PAM configuration/account-status categories
   within the guarded attempt. Never export raw terminal bytes, passwords or
   shadow hashes, or weaken real PAM/Polkit policy to pass.
3. Qualify `test_authenticated_request_revalidates_live_state` (child-role,
   approver-role, preferences × child1/kiosk). The six cases now ran and reached
   their real prompt and intentional mutation, but failed authentication before
   broker revalidation. Successful PAM authentication followed by AccessDenied
   and unchanged post-mutation state remains unproven. Keep these cases before
   successful grants so the real per-caller cooldown does not block prompts.
4. Qualify `test_real_selected_parent_authentication[child1]` and `[kiosk]`:
   selected password accepted, live grant, other accounts unchanged, and no
   reusable broker or AccountsService management authority. Both wrong-password
   checks pass; assertions after valid authentication remain unexecuted.
5. Finish stale/deleted-child, selected-approver identity/eligibility, and
   requester-disconnect cases using real system-bus names. Include completed
   authentication after requester disconnect where feasible, distinguishing
   broker revalidation from authentication cancellation. Use isolated fixtures
   or restore mutations, and compare state after intentional account changes.
   The existing six mutations are not the complete matrix. Audit root's explicit
   management allowance in the interface table as well as ordinary admin roles.
6. Finish evidence-backed broker/account mappings in `tests/requirements.json`
   (still `planned`). Do not claim unexecuted authentication, in-flight or
   graphical coverage. Run the expanded guarded suite, inspect redacted logs,
   run `make check` and `git diff --check`; complete the single master Task 14
   entry only after every deliverable passes. Stop before Task 15A.

### Accepted interfaces and current edits

Reuse [the installed runner contracts](../../tests/integration/README.md#reusable-implementation-contracts),
`FixturePassword`, `PersistentCaller`, and `TextAgent`. Agent registration uses
`pkttyagent --process PID,START_TIME`, a private controlling PTY and notification
pipe. Prompt readiness verifies selected identity and echo-off state. Cleanup
signals only directly spawned pidfd-pinned processes. Credentials stay in memory
and are installed through stdin without diagnostic export.

`TextAgent.authenticate` now consumes the first complete terminal outcome and
reports fixed accepted/denied/cancelled categories, rejecting unexpected outcomes
immediately. Fragmented markers, stream ordering, both opposite outcomes and
secret-free errors/output have focused regressions in `test_system_agent.py`.
This behavior was exercised in the latest VM attempt. The marker handling follows
[upstream Polkit's text listener](https://github.com/polkit-org/polkit/blob/master/src/polkitagent/polkitagenttextlistener.c).

`system_runner.PHASE_COUNTS['authorization'] == 221`; latest guest XML confirms
221 executed cases. No test selector or phase-count change in this continuation.
This continuation edited `system_caller.py`, `system_guest.py`, the existing
untracked `test_system_agent.py`, this handoff and the reusable runner guide.
Activation `none`; no packaged integration, migration, host dependency change,
product installation on the host or commit. Preserve all pre-existing edits.

### Verification and next run

- Isolated prerequisites, before integrated process cleanup:
  `/usr/bin/python3 -B -m pytest tests/unit/test_system_agent_cleanup_safety.py tests/unit/test_system_caller_cleanup_safety.py tests/unit/test_system_runner_cleanup_safety.py tests/unit/test_prepare_host_cleanup_safety.py tests/unit/test_child_preview_cleanup_safety.py -q`
  — **43 passed, three subtests passed** this continuation.
- Focused helper/guest tests: **38 passed**. `make check` after the post-attempt
  journal correction: **843 unit/contract and 17 component tests passed**, with
  stage traceability.
- `git diff --check` passed after handoff edits.
- Latest fresh build: `/tmp/onpc-task14-20260906T0409/first`.
  Package SHA-256:
  `2e17b7abfb42d8ec3a23f0a0a89ca43ba4c7b0a8853448d83e406bec96895153`.
  Source revision `093d218b4c927908a86b5121ab55138435437716`;
  build source digest
  `b184fe3ea6b592a8c721a48c7043c3f2aeabb9a18e1b8a61dab32c71f9ca6ca8`.
  The package bytes match the earlier daily build. The builder's source digest
  covers **all tracked/untracked source inputs**, including tests and docs;
  do not describe it as a package-only input digest. The collector correction
  and this handoff postdate this build and the frozen VM test inputs.
- Prepare current inputs with
  `make build-test-artifacts OUTPUT_DIR=/tmp/<new-empty-directory>`, then use
  `pkexec make -C /Data/Code/PST/parent-control check-system ARTIFACT_DIR=<verified-directory>`
  with platform sandbox escalation. The existing runner takes about seven to
  nine minutes for baseline/install/reboot/authorization/cleanup. Never run the
  guest pytest suite directly on this host or bypass guards to select cases.

### Evidence and clean machine state

Latest failed attempt: `/tmp/onpc-system-lc5oclev/evidence/`.
`guest/authorization.xml`: **213 passed, eight failed**, no errors/skips,
95.331 seconds. Each failure is `agent:unexpected-denied`, listed above.
`guest/installed.xml` and `guest/rebooted.xml`: two passing tests each.
`result.json`: `outcome=failed`, `category=command:failed:ssh`,
`cleanup_phase=complete`; the category reflects guest pytest failure, not an
SSH connectivity failure. Broker/service exports contain no `Traceback`,
`CRITICAL` or `ERROR` matches. The empty authentication journal is failed
collection evidence, not evidence that PAM logged nothing.

The runner restored the retained baseline and prior domain configuration and
verified host product/PAM preservation. Independent
`virsh --connect qemu:///system domstate ubuntu26.04` returned `shut off`.
The user briefly interrupted the turn; the original runner remained active and
was resumed to completion. No duplicate run was started. All commands exited;
no recovery or process resumption is pending.

Preserve earlier failed evidence at `/tmp/onpc-system-8g4zlvv1/evidence/`,
`/tmp/onpc-system-z5avn5xw/evidence/` and `/tmp/onpc-system-4blqk7sg/evidence/`,
and passing 213-case evidence at `/tmp/onpc-system-7utjj2ct/evidence/` and
`/tmp/onpc-system-61fofrz8/evidence/`. Later success never relabels failures.

This is a clean checkpoint after the requested ten-minute interval. Resume by
saying `Run docs/Test-Automation.md`.
