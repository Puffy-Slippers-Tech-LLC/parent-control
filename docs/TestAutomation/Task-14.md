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
both paths. The method/role audit and a corrected full authorization-area run
now pass, including direct private-record write-open denials and active-prompt
approver locking. The [finite coverage audit](Evidence/Task-14-Coverage-Audit.md)
records the remaining independent eligibility predicates; do not repeat the
method audit. The noninteractive-administrator boundary now has installed
assertions and a broker fix; unsafe-name fixture locality and independent exclusion
now pass after bounded public readiness observation. Real OpenLDAP/SSSD standard
and administrator fixtures now pass public classification, discovery exclusions,
direct selections and remote caller checks. The broker locality requirement for
management is fixed and verified. The final full-area acceptance passed; preserve
all registrations as regression coverage.

<!-- Preserve incoming links from historical evidence records. -->
<a id="continuation-handoff--2026-09-06-incomplete"></a>

## Completion handoff — 2026-09-06 (accepted)

**Completed this session:** built verified current inputs and ran the complete
registered authorization area once. All **233 executions** passed: 229
authorization cases plus four installation/reboot prerequisites. Exact expected
and executed identities match without duplicates, failures or skips. Product,
infrastructure, collection and cleanup all passed. Reviewed redacted broker
logs and eligibility/remote/authentication evidence. Task 14 is checked complete
in the master backlog; no Task 14 implementation or acceptance remains.

**Verification:** `make check` passed **1,293 unit + 17 component tests** and
source/traceability checks. Isolated safety selection passed **49 + 3 subtests**;
the privileged dispatcher passed **175 + 3 subtests** before VM operations.
`git diff --check` passed. One VM attempt, recorded stages **516.706 seconds**;
no new investigation or rerun. [Commands, hashes and evidence](Evidence/Task-14-20260906-Final-Acceptance.md).
This is Task 14 acceptance, not complete system or graphical E2E acceptance.
Broader account/customer requirements retain their pending scope.

**State:** evidence `/tmp/onpc-system-9670iwjl/evidence`; build session **9454**,
local check **42905** and VM controller **98893** all exited **0**. Baseline
restoration/verification completed and `ubuntu26.04` was independently confirmed
**shut off**. No owned operation remains. Scope is the development host and
existing guarded VM. Only documentation changed after verification; no host
product/account changes were made.

**Next result:** begin [Task 19A's first slice](Task-19.md#task-19a):
establish the E2E scenario inventory/selection contract and host-safe validation,
reusing 19P's proven worker, transport and lease instead of repeating feasibility.

**Next-session settings:** `gpt-5.6-sol` / `high`; model: keep; effort: raise.
**Reason:** suite acceptance is complete. The next bounded slice needs careful
scenario/evidence and guard contract design; the existing backend implementation
keeps it within the same model's scope, with higher reasoning effort.
