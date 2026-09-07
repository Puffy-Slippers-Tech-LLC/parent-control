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

**Next result:** after F1, distinguish the reason for the helper's
`authority-response` failure in the selected-parent case. The stage is now known;
do not rerun merely to rediscover it. Task 14 remains unchecked.
**Next-session settings:** `gpt-6-astra` / `high`; model: keep; effort: keep.
**Reason:** real authentication still fails at an unresolved security boundary;
the difficult diagnosis remains. Confirm both at the start of the session.
The authorized scope
is this development host and the existing guarded `ubuntu26.04` VM. Follow the
[current continuation](Continuation.md); F1 and 19P are now accepted, and this
authentication diagnosis is the next unfinished slice.

**Known:** latest `/tmp/onpc-system-vbx_zcy6/evidence/guest/authorization.xml`
records 213 passed and eight `agent:unexpected-denied` failures in 91.459 s.
Registration and selected-identity prompts work. Earlier journal evidence has
Polkit denial events for all ten challenges, while only the two deliberate
wrong passwords have PAM authentication-failure journal entries. This does not
establish successful PAM/account checks or the cause of valid-password denial.

**Now exercised during F1:** `system_caller.TextAgent.authenticate` reduces
private helper stderr to allowlisted PAM-authentication, PAM-account,
identity/authority-response, or unknown categories. The selected run at
`/tmp/onpc-system-sjmucss6/evidence` exercised this code (JUnit's helper line 185
also corroborates it). A read-only, allowlisted search of that run's retained
host-private command output found `pam-authenticate` for the deliberate wrong
password, then `authority-response` for the valid-password attempt. This narrows
the failing boundary; it does not establish why the authority response failed.
Neither category reached that earlier run's exported guest evidence. F1's final
unselected run now exports all ten reduced per-attempt records: two
`pam-authenticate` wrong-password denials and eight `authority-response`
valid-password denials. Exact case/attempt associations, redaction, original
failures and cleanup passed the [F1 acceptance audit](Evidence/F1-Qualification-2026-09-06.md).
This establishes the export boundary, not the authority failure's cause. Reuse
`FixturePassword`, `PersistentCaller`, `TextAgent` and the
[runner contracts](../../tests/integration/README.md#reusable-implementation-contracts).
Do not revisit resolved registration/terminal-marker theories without new evidence.

**Next experiment:** first inspect the retained evidence and authority-response
handling; identify a safe discriminating reason/status to capture and validate
its collection locally. Only then run F1's selected
`test_real_selected_parent_authentication[child1]` with its real prerequisites.
Several earlier full runs and two F1 selected failures have already exercised
this flow. The two-attempt limit is already spent; no unchanged rerun is justified.
Do not revisit registration/terminal-marker theories or change passwords/policy
speculatively. F1 acceptance does not depend on repairing this authentication.

**State/evidence:** the recorded runner completed cleanup, restored the baseline
and domain configuration, preserved the host, and left the VM off. No operation
was pending at that checkpoint; verify ownership before a new attempt. Preserve
unrelated concurrent edits. [Recorded checks, artifact digests and earlier
attempts](Evidence/Task-14-2026-09-05.md) remain evidence for their inputs. The
[F1 acceptance record](Evidence/F1-Qualification-2026-09-06.md) supplies the newer
verified artifacts and exported diagnostic identities. Verify package-input
applicability before reusing them for a changed-source attempt.

**Remaining:** basic authentication on both surfaces; in-flight matrix;
stale/removed identity and eligibility; completed authentication after requester
disconnect where feasible; root management; evidence-backed requirement mappings
and full task acceptance. The [standard session prompt](../Test-Automation.md#continue-implementation-in-fresh-sessions)
resumes the recorded continuation; this handoff preserves Task 14 while its
prerequisite work proceeds.
