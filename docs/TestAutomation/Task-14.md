### Task 14 — Test installed broker identity and authorization boundaries

- Depends on: [F1 focused diagnosis](Task-F1.md) and the implemented
  [installed runner](../../tests/integration/README.md). Reuse existing Task 14 work.
- Complexity: very high. These are security boundaries that cannot be proven by
  same-UID mocks.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Model rationale for remaining work: establish the authentication failure
  boundary before expanding installed in-flight revalidation and disconnect cases.
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
  - After F1, run the complete registered authorization area and its required
    prerequisite phases, `make check`, and `git diff --check` for task acceptance.
    Use a registered case selector for diagnosis; keep all matrix cases pending
    until their own assertions execute. No guest pytest invocation on the host.
- Completion criteria: every method/role cell in the
  [broker interface matrix](../SystemDesign/Broker.md#broker-interface-and-roles) has an
  installed-system assertion and cross-account attempts fail closed.

## Implementation slices

Follow the [bounded workflow](Implementation-Workflow.md). First exercise the
existing helper diagnostics on one selected-parent case: deliberate wrong
password, then a valid password and actual grant. Do not add more dependent
mutation cases while this path fails. Next prove one successful authentication
followed by changed-state denial; then parameterize the required matrix and
finish stale/deleted accounts, selected identity/eligibility, requester
disconnect and root's management allowance. Preserve existing test registrations.
Use isolated fixtures/cooldowns; a selected case must not require unrelated
cases to run first. Finish with the full authorization area once.

## Continuation handoff — 2026-09-05 (incomplete)

**Next result:** after F1, identify the exact helper failure stage in one real
selected-parent authentication case. Task 14 remains unchecked.
**Next-session settings:** `gpt-6-astra` / `high`; model: keep; effort: keep.
**Reason:** real authentication still fails at an unresolved security boundary;
the difficult diagnosis remains. Confirm both at the start of the session.
The authorized scope
is this development host and the existing guarded `ubuntu26.04` VM. Follow the
[current continuation](Continuation.md); finish F1 before further diagnosis.

**Known:** latest `/tmp/onpc-system-kpjcrm54/evidence/guest/authorization.xml`
records 213 passed and eight `agent:unexpected-denied` failures in 94.800 s.
Registration and selected-identity prompts work. The corrected journal collector
works; all ten challenges have Polkit denial events, while only the two deliberate
wrong passwords have PAM authentication-failure journal entries. This does not
establish successful PAM/account checks or the cause of valid-password denial.

**Changed but unqualified:** `system_caller.TextAgent.authenticate` now reduces
private helper stderr to allowlisted PAM-authentication, PAM-account,
identity/authority-response, or unknown categories. Its focused regressions and
host checks passed; this diagnostic change **has not run in the VM**. Reuse
`FixturePassword`, `PersistentCaller`, `TextAgent` and the
[runner contracts](../../tests/integration/README.md#reusable-implementation-contracts).
Do not revisit resolved registration/terminal-marker theories without new evidence.

**Next experiment:** validate the new category handling locally, then use F1's
listed selector for `test_real_selected_parent_authentication[child1]` with its
real prerequisite closure. Capture the category and safe account/PAM status
needed to distinguish authentication, account-management and authority-response
failure in the same attempt. Several earlier full runs have already failed at
this boundary; this is an instrumented discriminating attempt, not a reset of
the two-attempt limit. Do not change passwords or policy speculatively.

**State/evidence:** the recorded runner completed cleanup, restored the baseline
and domain configuration, preserved the host, and left the VM off. No operation
was pending at that checkpoint; verify ownership before a new attempt. Preserve
unrelated concurrent edits. [Recorded checks, artifact digests and earlier
attempts](Evidence/Task-14-2026-09-05.md) remain evidence for their inputs; the
package build predates the new diagnostics. Verify applicable inputs or rebuild.

**Remaining:** basic authentication on both surfaces; in-flight matrix;
stale/removed identity and eligibility; completed authentication after requester
disconnect where feasible; root management; evidence-backed requirement mappings
and full task acceptance. The [standard session prompt](../Test-Automation.md#continue-implementation-in-fresh-sessions)
resumes the recorded continuation; this handoff preserves Task 14 while its
prerequisite work proceeds.
