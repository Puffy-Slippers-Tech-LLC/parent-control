### Task 14 — Test installed broker identity and authorization boundaries

- Depends on: [F1 focused diagnosis](Task-F1.md) and the implemented
  [installed runner](../../tests/integration/README.md). Reuse existing Task 14 work.
- Complexity: very high. These are security boundaries that cannot be proven by
  same-UID mocks.
- Recommended Codex model: `gpt-6-astra`
- Recommended reasoning effort: `high`
- Initial model rationale: establish real authentication and identity boundaries.
  The current handoff reevaluates settings for the remaining slice.
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

Follow the [bounded workflow](Implementation-Workflow.md). Both child and kiosk
selected-parent cases now prove deliberate wrong-password denial, a valid
password and an actual grant. All six authenticated live-state revalidation
variants and the previously registered authorization area have passed.
Root's method permissions, stale/deleted selections, and authenticated in-flight
target deletion on both request surfaces now pass in focused VM selections.
Requester disconnect/cancellation and fresh-connection recovery now pass on
both paths. Next reconcile the method/role and account-requirement coverage,
batch any concrete missing identity/eligibility assertions, and finish acceptance.
Preserve existing registrations.
Use isolated fixtures/cooldowns; a selected case must not require unrelated
cases to run first. Finish with the full authorization area once.

## Continuation handoff — 2026-09-06 (incomplete)

**Next result:** finish the finite Task 14 coverage audit and acceptance. Compare
the registered installed cases with the broker method/role matrix and explicit
account requirements. List any concrete missing identity/eligibility assertions,
implement only those gaps as a batch, update requirement mappings, then run one
complete authorization-area acceptance. Do not carry forward an undefined
“remaining variants” investigation or repeat completed focused matrices just
to resume. Task 14 remains unchecked. Scope: development host and existing
guarded `ubuntu26.04` VM.

**Next-session settings:** `gpt-5.6-sol` / `medium`; model: keep; effort: lower.
**Reason:** live authentication and cancellation ordering are resolved. Coverage
reconciliation and mappings can use the proven installed helpers with medium
effort; reassess only if the audit identifies a new concurrency boundary.

**Completed this session:** registered requester disconnect/cancellation and
fresh-connection recovery for both child and kiosk. The bus name disappeared
during a real prompt; Polkit denied the vanished subject. Closing the owned
agent then released the transaction. Correlated broker denial, no write-stage
entries and unchanged state across all seven role accounts were verified.
Each surface then authenticated with the same credentials on a fresh connection
and received a real grant; cleanup revoked it and respected the cooldown.
This proves explicit agent cancellation, not automatic prompt dismissal or a
separately forced post-approval `caller_alive` branch.

**Verification:** third VM attempt passed all **five exact executions** and all
four outcome domains. First failure disproved successful authentication after
subject exit; second established that terminal failure alone does not complete
the transaction. Both failures remain retained; the third followed that concrete
lifecycle correction. **146 focused tests**, **30 isolated safety tests**, and
dispatcher **175 tests / 3 subtests** passed. Final `make check`: **1,225 unit/
contract and 17 component tests** passed. Seven selected hashes match; **275**
public guest files passed the scoped identity scan.
[Evidence, commands, all attempts and timings](Evidence/Task-14-2026-09-06-Requester-Disconnect.md).

**Remaining:** requirement/method-matrix audit and full-area acceptance, including
the extracted stale-selection helper and new disconnect case together. No active
blocker remains. Preserve [in-flight deletion](Evidence/Task-14-2026-09-06-InFlight-Deletion.md)
and [stale-selection](Evidence/Task-14-2026-09-06-Deletion-Qualification.md)
evidence. Full Task 14 and release acceptance are pending.

**State:** final build **42128**, VM **14234**, checks **90893**, and manifest
read **15742** exited **0**. Evidence: `/tmp/onpc-system-8zftfkk4/evidence`.
Baseline restored, domain **shut off**, all owned operations finished. The slice
overran its estimate to complete the evidence-based correction and cleanup.
