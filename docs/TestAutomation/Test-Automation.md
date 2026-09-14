# Remaining test automation implementation

This backlog owns task order and completion. The
[daily guide](../Test-Automation.md) owns commands and the
[workflow](Implementation-Workflow.md) owns execution and handoff.

## Operator scope — 2026-09-14

Prioritize customer E2E scenarios generally, across all product surfaces and
journeys. Timeout/login rejection is an illustration, not a special priority
or the limit of coverage. Each customer test operates and
observes the app as a real customer; internal product probes and backend
corroboration are outside its acceptance. Follow
[E2E-Coverage.md](E2E-Coverage.md), which supersedes contrary historical task
instructions and pending inventory assertions.

Keep completed unit, component, installed and harness tests as they are.
Existing regression/safety execution remains required where applicable.
Keep mechanical installation, upgrade, migration, removal and recovery checks
in Tasks 18/20, including necessary internal inspection. Their depth is not a
template for customer E2E.

The unfinished [policy-acknowledgement design](Policy-Acknowledgement.md) is a
separate product decision, not an E2E prerequisite. Other deferred internal
qualification remains explicitly listed below. Deferral does not mean passed,
unnecessary, or safe to delete.

## Implementing one task

Start with one complete named customer variant and its visible finish line.
Reuse accepted graphical input, fixture provisioning, installation setup,
credentials, evidence and cleanup. Bring forward only a helper needed by that
specific variant; no whole installed-system or UI-matrix task is a prerequisite
merely because it previously owned a helper.

Finish edits before build/run/collection/cleanup. Use the existing validated
runners and VM guards. Check off a task only after its finite assigned customer
variants pass; registration and helper qualification are not acceptance.

The implementation agent also owns each scenario's
[runtime registration and discovery check](E2E-Coverage.md#register-each-runnable-scenario-within-its-implementation-task)
within that same task. Completed variants must be runnable and registered
`ready` so `make test-all` automatically includes them. The operator has no
manual registration step; do not postpone this work to Task 28.

A demonstrated product failure remains a failed case with a reproduction and
an explicit product-repair blocker. Customer E2E workers do not investigate
internal mechanisms. Continue independent variants; if none is ready, stop for
a repair/scope decision instead of resuming deferred engineering automatically.

## Shared implementation and acceptance rules

- Customer actions and assertions use screens and normal interaction. Other-user
  checks use that user's desktop; persistence uses reopen/login; app enforcement
  uses actual launch/use. No PAM, D-Bus, private files, rules, grants, PIDs or
  transaction witnesses are customer assertions.
- Existing safeguards for VM ownership, secret input, provenance, bounded waits,
  artifacts and cleanup remain required. Add infrastructure only for a named
  customer step that cannot run safely through existing interfaces.
- Natural expiry uses real elapsed time. No private state writes, forced locks,
  fake clocks, mocks or mid-journey restores construct customer outcomes.
- Setup may use supported helpers. Feature tests require verified installation;
  they do not wait for the entire clean-install qualification.
- Installation/package qualification may inspect internals and induce its
  declared failures. Retain Task 20's recovery ledger and checkpoints. Charge
  actual shared R1 repair to that ledger; it cannot silently become a broad
  prerequisite for every customer case.
- A shared visible journey has one canonical executable and may satisfy multiple
  task mappings. No duplicate execution merely to complete another task number.
- Existing tests and required safety checks remain intact. Run affected checks
  for implementation edits; do not expand lower-level matrices as E2E work.

## Requirement and evidence maintenance

The executable inventory and requirement mappings still reflect the earlier
plan. This documentation session changes no runtime status or schema.
Reconcile each affected declaration with the surface-only contract when its
first customer consumer is implemented, including only the minimum shared
validator adaptation needed. Preserve safety fields; do not invent backend
evidence to satisfy legacy mandatory assertions.

Explicitly record moved internal obligations under their separate owner.
Reclassification, removal of duplicate planned variants and changed denominators
are scope changes, never completed scenarios. Keep all distinct customer
behavior and both request surfaces. Missing external sending authorization
blocks only the applicable feedback case.

Only a complete run of the declared customer actions and visible assertions
earns E2E credit. Unit/component passes and engineering qualification retain
their own scope. A customer-suite pass does not certify deferred product
guarantees or substitute for mechanical package acceptance.

## Unfinished tasks

Select the earliest ready unchecked entry within the customer queue. If a
variant is blocked, record its evidence and return condition, then continue
independent customer work. Cross-task helpers can be introduced with their
first consumer; the entire owning task need not be accepted first. Reconcile
[Continuation.md](Continuation.md) at each handoff.

### Accepted foundation — retain unchanged

- [x] [Task F1 — Guarded installed selection and diagnosis](Task-F1.md)
- [x] [Task 19P — Graphical backend compatibility](Task-19.md#task-19p)
- [x] [Task 14 — Installed broker identity and authorization](Task-14.md)
- [x] [Task 19A — Guarded graphical worker and console transport](Task-19.md#task-19a)
- [x] [Task 19B — Stable screen matching and graphical smoke](Task-19.md#task-19b)

These remain engineering coverage, not completed customer journeys.

### Customer queue — first priority

- [ ] [Task 21A — Parent discovery, navigation, access and feedback drafting](Task-21.md#task-21a)
- [ ] [Task 21B — Parent saves, control changes and revocation](Task-21.md#task-21b)
- [ ] [Task 23A — Child-overlay approval, cancellation and retry](Task-23.md#task-23a)
- [ ] [Task 23B — Overlay choices, validation and exit](Task-23.md#task-23b)
- [ ] [Task 24A — Kiosk entry and request-only interaction](Task-24.md#task-24a)
- [ ] [Task 24B — Kiosk requests, choices and return to login](Task-24.md#task-24b)
- [ ] [Task 22A — Zero-time rejection, natural expiry and restored access](Task-22.md#task-22a)
- [ ] [Task 22B — Countdown display and visibility](Task-22.md#task-22b)
- [ ] [Task 25A — Application launch routes and matching](Task-25.md#task-25a)
- [ ] [Task 25B — App-window effects and other-user continued use](Task-25.md#task-25b)
- [ ] [Task 26B — Reopen, login, reboot and resumed use](Task-26.md#task-26b)
- [ ] [Task 26C — Complete everyday journeys and authorized feedback](Task-26.md#task-26c)
- [ ] [Task 26A — Remaining customer cancellation and retry gaps](Task-26.md#task-26a)

### Mechanical package qualification — after customer work

These retain their internal checks. Customer package journeys E2E-002/026/027
also remain required and may share one attempt with distinctly labeled
mechanical assertions. Their customer assertions still obey E2E-Coverage.md.
Unavailable or blocked customer cases do not require indefinite idle work;
record them before selecting ready package work.

- [ ] [Task 18A — Package activation classes and customer update behavior](Task-18.md#task-18a)
- [ ] [Task 18B — Migration interruption, retry and invalid data](Task-18.md#task-18b)
- [ ] [Task 18C — Mechanical removal/reinstall/purge and customer lifecycle](Task-18.md#task-18c)
- [ ] [Task 20 — Clean installation, reboot and startup qualification](Task-20.md)

### Acceptance and handoff

- [ ] [Task 28B — Review executed customer and package coverage](Task-28.md#task-28b)
- [ ] [Task 28C — Document the verified workflow and remaining limits](Task-28.md#task-28c)

### Separate engineering — not automatic fallback

| Retained work | Status/owner |
| --- | --- |
| Policy acknowledgement and probe protocol | [Separate design handoff](Policy-Acknowledgement.md); explicit product decision required. |
| Installed launch, confinement and rollback expansion | [15A/15B](Task-15.md); existing coverage retained, unfinished internal matrix deferred. |
| Time-authority, PAM, clock and session internals | [16A/16B](Task-16.md); customer behavior belongs to 22/26. |
| Session-entry races and reconciliation internals | [17A/17B](Task-17.md); customer behavior belongs to 22/25/26. |
| Non-installation induced faults and transaction races | [26A separation](Task-26.md#separate-engineering-obligations); preserve tests and explicit gaps. |
| General evidence/runner expansion | [27A–C](Task-27.md); only a concrete blocked consumer may bring forward a minimal adapter. |
| Broad four-command/CI/cache expansion | [28A](Task-28.md#task-28a); no standalone implementation before a concrete need or separate direction. |

These are unaccepted/deferred, not checked-off tasks. The launcher finishes the
active checklist and reports deferred work; it must not claim full-specification
or unrestricted release acceptance while an applicable product blocker remains.

## Progress baseline and accounting

At this documentation rewrite: **0 completed customer E2E variants**; the runtime
inventory has one ready harness smoke and 156 pending legacy variants, including
internal faults. This is a snapshot, not a new acceptance result or the final
customer denominator. Reconcile scope transparently with the first consumers.

Carry cumulative counts, accepted variant IDs/evidence, remaining frozen scope,
scope transfers and consecutive slices without a completed customer variant in
the active handoff/Continuation.md. Planning and helper tests do not advance
customer completion. The [workflow](Implementation-Workflow.md#handoff-format-and-cost-review)
defines intervention thresholds and keeps mechanical milestones separate.
