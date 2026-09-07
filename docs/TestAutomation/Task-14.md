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
Root's method permissions are now verified in a focused selection. Next finish
stale/deleted accounts, selected identity/eligibility and requester disconnect.
Preserve existing registrations.
Use isolated fixtures/cooldowns; a selected case must not require unrelated
cases to run first. Finish with the full authorization area once.

## Continuation handoff — 2026-09-06 (incomplete)

**Next result:** implement and verify stale/deleted identity assertions, beginning
with actual deletion of a selected target and approver, refreshed discovery and
fail-closed requests without changes to surviving accounts. Task 14 remains unchecked.
**Next-session settings:** `gpt-5.6-sol` / `high`; model: keep; effort: raise.
**Reason:** root permissions and the existing authentication helper are proven;
the next slice must distinguish NSS/AccountsService identity lifecycle and
broker revalidation, requiring more security reasoning than the root matrix.
Scope remains this development host and the existing guarded `ubuntu26.04` VM.

**Proven this session:** added explicit root opt-in to the guarded caller helper
and seven credential/agent regressions. One new installed case exercised all
17 root method cells, observable management writes, other-account isolation,
request-only denials, discovery/approver exclusion and log-component restrictions.
The focused run passed **five exact executions**, including four install/reboot
prerequisites; all four outcome domains passed. Isolated cleanup checks passed
30 tests, caller checks 25, and `make check` passed 1,210 unit/contracts plus
17 components and static/traceability checks. [Inputs and evidence](Evidence/Task-14-2026-09-06-Root.md).
The prior [225-execution area pass](Evidence/Task-14-2026-09-06-Authorization.md)
already proves both authentication surfaces and all six live-state variants.

**Next action:** extend `tests/system/test_authorization.py` using isolated
disposable account fixtures, `call`/`batch`, `account_state` and, where needed,
`PersistentCaller`. Establish the actual account-deletion observation before
asserting stale-identity denial; preserve other accounts and retained evidence.
Use host-safe collection, isolated safety prerequisites, fresh inputs and the
smallest registered selection. No deletion experiment has been attempted and
no unresolved root/authentication blocker remains. Do not repeat solved work.
Still missing: stale/deleted identities, remaining selected identity/eligibility
changes, requester-disconnect completion, final requirement/matrix audit and
complete-area task acceptance.

**State:** root run session 79852 exited 0; evidence is
`/tmp/onpc-system-o0xgf72y/evidence`. Baseline/domain restoration and host
preservation passed; final domain check was `shut off`. No operation is pending.
All new caller/system-test code was exercised in the VM; subsequent edits are
documentation only. One VM attempt, approximately 5.6 minutes of runner stages;
no retry. Prior working-tree edits remain preserved.
