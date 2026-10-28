# Kiosk usability repairs

Task queue: [Ordered task queue](Kiosk-Usability-Queue.md).
Next task: **U03a — [Restore entry after stale owned admission state](Kiosk-Usability-Tasks/U03a-stale-admission.md)**.

## Outcome and scope

Keep the passwordless request station usable through the specific availability
faults identified in the kiosk review. Repair demonstrated causes of rejected
entry, unavailable requests and failed recovery with the simplest change at the
existing owner. This is a usability repair plan, not a confinement-hardening or
general product acceptance campaign.

The [specification](Specification.md) owns behavior. Start source work at
[System design](System-Design.md); apply the kiosk design's
[usability priority](SystemDesign/Kiosk-Confinement.md#usability-priority-and-reasonable-child-effort)
and [recovery boundary](SystemDesign/Kiosk-Confinement.md#admission-defaults-and-recovery).
Preserve genuine authentication, enforcement, explicit administrator denials and
live/foreign-state ownership. Never turn a PAM error into success, enable global
empty-password authentication, replay approval or fall back to a full desktop.

The motivating findings are source-level risks, not measured failure rates:
non-C locale requirements can stop approval; global child-extension refresh can
stop the broker; admission contention, stale owned state, helper failures and
interrupted configuration can reject entry. Essential-service and optional
presentation paths need a bounded check for the same availability coupling.
Verify each finding against current code and existing coverage before editing.
An effective existing path needs verification, not replacement infrastructure.

Exclude terminal/TTY/SSH and escape-route work, new protective predicates,
arbitrary host/package matrices, performance campaigns, feature catalogues,
all-language UI matrices and broad broker redesign. Do not restore private
loaders, material inventories or runtime preparation frameworks.

## Per-task acceptance boundary

Each installed task owns one finite fault/recovery history on Ubuntu and Fedora,
using maintained operations and explicit timeouts. No selector is implemented
merely because a brief names a condition. Discover registrations before use;
add only missing finite bindings at their existing test owner. Apply the
[test scope mandate](Mandates/Test-Scope-Mandate.md) and
[system acceptance contract](TestAutomation/E2E-Execution-Contracts.md#system-acceptance).

Before implementation, select the exact fault, expected recovery action and
smallest affected checks. Record those choices in the current brief/checkpoint,
not a separate evidence document. Restoration must lead to usable requests;
safe refusal alone does not complete a recovery task. If the selected condition
already works, verify it and record that no product change was needed.

For entry/lifecycle repairs, observe the exact fault, supported recovery, fresh
passwordless entry to a usable form, one genuine approval with independently
observed intended time access, exit and fresh usable reentry. For request-only
repairs, use one entry and the affected request/recovery sequence. Add ordinary
account login only for shared PAM/session changes; add an overlay request only
if its shared caller changes. Cover denial/Cancel without a grant at the lowest
effective layer, retaining installed controls when authentication association or
dispatch changes. Check soft/hard app effects only if the fix changes that policy.
Human reading, language choice and authentication are not startup deadlines.

## Task sizing

Locale availability and locale-discovery failure are separate tasks (U01/U01a),
as are temporary admission contention and stale owned state (U03/U03a). Each
owns its fix, focused checks and cleanup. Do not combine their fault histories
into one implementation assignment.

The queue marks longer installed tasks as session exceptions: each retains one
finite fault/recovery history on both declared targets. U02's healthy-child and
restored-child observations belong to the same isolation history; U05/U06 retain
their interrupted-configuration/update lifecycle boundaries. These estimates
include implementation, checks, required review/build and cleanup, not just test
runtime. Follow the shared [sizing contract](TestAutomation/E2E-Execution-Contracts.md#task-size-and-order):
extract newly discovered independent work before implementation, but keep each
complete installed history together. Do not create separate implementation and
verification rows or shorten acceptance to fit a session.

## Recovery results

Fault injection and state probes are engineering checks; successful customer
results use public actions after restoration. A painted window, account-only PAM
probe, diagnostic-only form or successful callback is insufficient. Keep safe
retry/exit when an essential dependency remains unavailable. Recovery must not
silently relax enforcement or retry an uncertain mutation or authentication.

There is no final all-features journey or repeat of every preceding task.
Checked rows stay done under the shared
[completion policy](Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery).
Only a concrete later change invalidating an earlier path earns its affected
checks within that later task. Keep normal failure diagnostics and short queue
results, not a new proof archive or acceptance framework.

An unresolved defect in a row's selected recovery path keeps that row unchecked,
with its concrete blocker and return condition. A limitation outside that finite
path may be recorded without expanding the task or claiming it was repaired.

## Execution and ownership

Follow [Approval tools](Approval-Tools.md), [Execution plans](Execution-Plans.md)
and the [test documentation map](TestAutomation/README.md). Read applicable
VM/UI/storage mandates before their operations. Use `make install` only on
authorized installed test targets, never install the product on the development
host, and run `make build` after final packaged-input edits. Product strings
need all supported languages; What's New synchronization is separately authorized.
Run scoped host regressions and obtain the required independent Astra xHigh
review for core backend changes before installed close-out.

The coordinator is GPT-6.1 Sol High, with the shared session budgets, supervision,
goal activation, attachment/stop, owned cleanup and commit/push/propagation.
Keep one editor per shared owner. Bound new prerequisites to the selected fault;
unrelated failures remain with their existing owner rather than expanding this plan.

The [accepted baseline](TestAutomation/E2E-Building-Blocks.md#c05f-fedora-baseline-acceptance)
is context, not a fresh-candidate pass. Reuse applicable completed checks without
reopening old reports. This new master has its own shared namespace; do not
migrate or abandon another launcher's checkpoint, pending Git transaction or VM
lease. Do not execute overlapping work concurrently.

U01–U08 overlap availability concerns in C09a–C09c1 of the
[confinement plan](Kiosk-Session-Confinement-New-Plan.md#task-boundaries).
Reuse delivered fixes and qualified operations; close only this queue's rows.
General feature automation and reliability work retain their existing owners.
This plan neither tightens confinement nor claims final confinement or release
qualification, and Fedora results do not broaden release support.

```sh
tools/kiosk --check
tools/kiosk --tasks 1
tools/kiosk --tasks 0
tools/kiosk --stop
```

These are alternatives. Default execution selects one task; `--tasks 0` selects
all remaining tasks. Omitted `--vm` uses configured enabled targets without
removing either brief's required target. The generic entry shares the same owner:

```sh
tools/execute-plan --plan 'docs/Kiosk-Usability-Plan.md' --check
```

New executable grants join at the next normal
[rules refresh](Approval-Tools.md#one-time-setup); the generic entry is available
under the existing grant meanwhile. No shared launcher or permission framework
changes are required.
