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
management is fixed and verified. Preserve all registrations; only final
full-area acceptance remains for Task 14.

## Continuation handoff — 2026-09-06 (incomplete)

**Next result:** run the complete registered authorization area against a fresh,
verified current-input build. If it and `make check` / `git diff --check` pass,
accept Task 14 and advance the continuation to the next master-checklist task.
The finite eligibility gaps are resolved; do not repeat remote fixture research,
method audits, or solved name/locality/deletion/disconnect investigations.

**Next-session settings:** `gpt-5.6-sol` / `medium`; model: keep; effort: lower.
**Reason:** real LDAP/NSS/AccountsService provisioning and broker remote-caller
exclusion are now proven. Remaining work is registered-suite acceptance and
review using established helpers, so medium effort should suffice.

**Completed this session:** implemented guarded OpenLDAP/SSSD fixtures and
`test_remote_accounts_are_excluded`, with selected-input provenance and declared
prerequisites. Both directory identities resolve through NSS and public
AccountsService as nonlocal, nonsystem, unlocked and interactive, with safe
names and verified standard/admin roles. Discovery exclusions, child/kiosk
approver selection, remote child targets, and both real remote callers pass;
all six direct boundaries return `AccessDenied`, with seven local accounts'
state unchanged. Fixed broker management authorization to require locality as
well as administrator status, preserving root; added revalidation regression.

**Verification:** two selected attempts. First failed fixture installation on an
obsolete SSSD pin; live archive verification resolved it to `2.12.0-1ubuntu5.4`.
Second passed all five executions and all four outcome categories. No remote
fixture blocker remains. `make check`: **1,293 + 17 passed** before the pin-only
correction; **93** focused tests passed afterward. Full-area acceptance remains
pending. [Evidence, commands, hashes and timings](Evidence/Task-14-20260906-Remote.md).

**State:** successful evidence `/tmp/onpc-system-1rwcidgj/evidence`; build
**46285** and VM **92878** exited **0**. First failure retained at
`/tmp/onpc-system-_7_od9yt/evidence`, with completed cleanup reconciled after user
interruption. Final VM state confirmed **shut off**, baseline restored, all
operations finished. Only documentation followed the successful VM run. Scope
remains this development host and existing guarded `ubuntu26.04` VM; no host
product/account changes or new VM. Existing uncommitted work is preserved.
Task 14 stays unchecked until final authorization-area acceptance.
