# Customer end-to-end scenario coverage

**Operator scope — 2026-09-14:** customer E2E automation uses the installed app
and observes it as a customer would. A step or assertion requiring internal
product inspection is outside customer E2E. This supersedes older backend
corroboration requirements in pending declarations and historical handoffs.
The [master plan](Test-Automation.md) prioritizes customer journeys.

## Scope tests around the app

Keep these kinds of work separate:

| Work | Scope and acceptance |
| --- | --- |
| Existing unit, component, installed and harness regressions | Preserve code, assertions, registration and evidence. Continue applicable regression and safety checks; this change does not weaken completed tests. |
| Installation, upgrade, migration and removal | [Task 18](Task-18.md) and [Task 20](Task-20.md) retain internal checks for mechanically correct packages, service ordering, permissions, cleanup and recovery. Label these package/system qualification, even when they also use the GUI. |
| Customer E2E | Real customer actions followed by visible results. No internal policy, process, service, storage or transaction assertions. |

For example: the parent sets zero time, the child enters the correct password,
and GDM rejects login with the time-limit message. That visible rejection and
absence of desktop access are sufficient. Do not inspect PAM return codes,
AccountsService, usage records, logind, D-Bus, rules or daemon acknowledgements.
A separate positive login case proves usable access when time is available.

Observe other-user isolation by switching to that user's desktop and using
their app; persistence by reopening the app or logging back in; blocking by
attempting the normal launch and observing the window or terminal output.
Do not substitute PIDs, kernel labels, stored preferences or backend receipts.

Customer E2E does not certify internal ordering, atomic commits, exactly-once
execution, complete rule parsing or absence of every race. The unresolved
[policy-acknowledgement design](Policy-Acknowledgement.md) is separate and is
not a prerequisite for observing customer behavior.

## Prepare prerequisites through supported helpers

Reuse existing guarded setup for accounts, installed packages, application
assets and synthetic attachments. Fixtures/infrastructure may verify their own
safe setup; these checks are not customer assertions or coverage credit.
Ordinary feature journeys need verified installation, not completion of
Task 20's entire installation qualification.

Once a journey begins, configure tested settings, authenticate, approve,
revoke, launch, switch users and exit through real customer interfaces. Never
write private settings/grants/usage, invoke broker methods, manipulate the
clock or force a lock to manufacture the result. Provision unrelated assets
through supported helpers; Ubuntu account-creation UI, game installers and
third-party account setup are not product targets. A dynamic-discovery fixture
may create an account while Parent is open; observe Parent discovering it.

Retain the existing VM lease, pinned VM, source/package integrity, secret-safe
input and owned cleanup. These safeguards do not authorize product probes.
Add only the smallest missing adapter required to execute or observe a named
customer step safely, qualify it with that consumer, then return to the journey.

## Customer journeys must exercise the real machine

- Use real installed Parent, child overlay, kiosk, GDM and desktop sessions.
  Send keyboard/mouse input through the accepted graphical backend and inspect
  displayed results. Customer command-line operations use the guest terminal.
- Passwords go into the real system prompt through existing secret-safe input.
  Check rejected/cancelled requests through the response, preserved choices,
  continued access restriction and a subsequent real retry.
- For natural expiry, select a supported short duration and let time elapse
  during actual use. Configured zero-time denial does not also prove exhaustion.
- Keep journeys continuous. No reconstructed intermediate states, checkpoint
  resume, mid-journey restore or mocked services. Restore the retained baseline
  only outside whole attempts; create no other VM, clone, overlay or snapshot.
- Observe retained app state by obtaining legitimate time, unlocking normally
  and finding the same window/activity. Do not inspect processes while locked
  or claim an invisible lifetime guarantee.
- Reboot, logout, suspend and wake use customer interfaces. Observe the return
  screen and resumed use; internal lifecycle proofs belong to package/system work.

## Distinguish supporting tests without weakening E2E

Customer E2E must not stop daemons, force desktop exposure, corrupt records,
inject transport failures, call private APIs or trace internal transactions.
User cancellation, invalid form input, app closure, reopening and retry remain
customer operations.

Preserve existing fault/security regressions. Unimplemented internal fault
matrices are separate engineering work, not customer prerequisites. Task 20's
startup faults remain required mechanical installation qualification.
Reclassify former non-installation E2E-028/029 backend-fault variants and
injected E2E-033 transport faults explicitly before implementing them; neither
their transfer nor their deferral is completed customer coverage.

A customer-visible product failure stays failed. Record its scenario, steps,
expected/observed result, evidence and affected cases in the task handoff.
Do not turn its E2E worker into an internal investigation. Retain the product
blocker separately and continue independent customer cases. If none can proceed,
stop for a separate repair decision. An unproven internal guarantee alone does
not block surface-only observation.

## Enumerate scenarios before implementing them

`tests/e2e/scenarios.json` remains the runtime inventory. This documentation
rewrite changes no schema, readiness flag or executable coverage. Legacy
declarations still contain mandatory backend assertions and internal faults.
At the first affected consumer, reconcile that scenario and only the minimum
shared validator/schema contract needed for surface-only acceptance. Preserve
IDs for the same visible behavior; explicitly record transferred obligations
and genuine non-applicability. Neither earns completion credit.

Do not fake backend values, keep mandatory product witnesses, weaken existing
safety validation or build a replacement evidence framework to satisfy stale
fields. Optional other-user assertions use customer screens/actions. Retain
the existing run/package identity, screen/step evidence, failure and cleanup
records. Backend product evidence is neither required nor collected.

Each variant needs finite preconditions, ordered customer actions, visible
expected results, a bounded duration and an executable selector.

| Family | Owner | Customer behavior or separate qualification |
| --- | --- | --- |
| E2E-001 | 19B/19A | Accepted harness smoke; no customer coverage credit. |
| E2E-002 | 20 | Visible install/reboot/login; separate mechanical startup/layout checks remain required. |
| E2E-003 | 21A | Launch Parent, discover/select children, observe dynamic discovery. |
| E2E-004 | 21A | Standard user cannot use management through the normal launcher. |
| E2E-005 | 21B | Save allowance/control changes, observe status and subsequent child access. |
| E2E-006 | 21B/25A | Change app rules, then attempt child launches. |
| E2E-007 | 21B/25B | Cancel/confirm revocation; observe time, app windows and another user's continued use. |
| E2E-008 | 22A | Configured zero-time fresh login rejection; separately, natural exhaustion, lock and unlock rejection. |
| E2E-009 | 22A | Grant expires; kiosk approval restores access with each soft-app choice. |
| E2E-010 | 22A | Other foreground user continues working while child time expires; child cannot resume without time. |
| E2E-011 | 22B | Countdown minutes/seconds and desktop/lock/GDM visibility. |
| E2E-012 | 23A | Overlay, parent selection, real authentication, approval and subsequent use. |
| E2E-013 | 23A/24B | Rejected/cancelled approval preserves visible choices and restrictions; retry succeeds. |
| E2E-014 | 23B/24B | Duration choices, representative invalid input and repeated submission. |
| E2E-015 | 23B/24B | Cancel, Escape and success produce correct visible exits/countdown. |
| E2E-016 | 24A | Kiosk entry and request-only access through normal desktop interactions. |
| E2E-017 | 24B | Child/approver selection and empty/ineligible/disabled states. |
| E2E-018 | 24B | Revisit both surfaces; choices persist and mute settings stay separate. |
| E2E-019 | 25A | Native/Snap/Flatpak apps launch or are blocked through supported customer routes. |
| E2E-020 | 25A | App update/removal and matching choices produce documented visible launch behavior. |
| E2E-021 | 25B | User switching and save/approve/revoke affect the intended user's app windows. |
| E2E-022 | 26B | Reopen, log out/in, reboot or suspend/wake; observe resumed use and preserved choices/access. |
| E2E-023 | 26C | Zero time → child denied → kiosk approval → gameplay → natural expiry → lock/unlock denial. |
| E2E-024 | 26C | Request more time during play, approve, continue and eventually expire. |
| E2E-025 | 26C | Replacement time before desktop return; observe each chosen app allowance. |
| E2E-026 | 18A | Customer update and resumed use; internal activation qualification is separately labeled. |
| E2E-027 | 18C | Continuous remove/reboot/login/reinstall/purge; mechanical cleanup is separately labeled. |
| E2E-028 | 20 / separate system work | Startup faults remain mechanical installation tests; other internal faults are outside customer E2E. |
| E2E-029 | 26A / separate system work | Customer close/cancel/retry only; transfer backend-induced failures and races. |
| E2E-030 | 21A | About/license through Parent. |
| E2E-031 | 21A | Feedback draft, validation, attachment review and cancel. |
| E2E-032 | 26C | With explicit sending authorization/test recipient, submit and observe the app's response; no claim of provider or recipient delivery proof. |
| E2E-033 | 26C / separate integration | Customer error/retry when reproducible through customer operations; injected transport faults remain separate. |

## Bound the matrix before expanding it

Freeze the selected variant's customer steps and visible finish line before
coding. Cover distinct behavior, supported routes, both request surfaces and
meaningful user-isolation cases. Group equivalent form values; do not multiply
routes by unrelated settings. Existing lower-level edge-case tests stay intact.
An internal state, hypothetical fault or new helper does not justify a variant.

Complete one runnable journey before expanding its matrix. Every new helper
names the blocked customer step and finite acceptance signal. Report additions,
transfers and deduplication separately from executed passes under the
[progress rules](Implementation-Workflow.md#handoff-format-and-cost-review).

## Required continuous example: E2E-023

1. Parent logs in, opens Parent, sets zero allowance and chooses game policy;
   observe the save.
2. Switch User, select child and enter the correct password; observe the
   time-limit rejection and no desktop access.
3. Enter kiosk, select child/approver, choose short time and authenticate;
   observe success and return to GDM.
4. Log in as child, launch a real installed offline game and interact with
   gameplay. Cover windowed and fullscreen variants with the same steps.
5. Let time expire naturally; observe lock and loss of game access.
6. Try the correct password; observe the time-limit rejection. End the
   journey and perform existing guarded cleanup.

Screens and interaction suffice. No grants, usage, process, rule or session
inspection is part of this example. Window recovery after another approval is
a separately declared customer path.

## Register each runnable scenario within its implementation task

The implementation agent owns registration, including during launcher-driven
work. Routine registration requires no operator edits, commands or approval.
Complete it for each scenario before claiming that scenario finished; do not
defer it until the whole lettered task, Task 28 or a manual follow-up.

1. Update the canonical entry in
   [scenarios.json](../../tests/e2e/scenarios.json), wire its executable path/test
   ID and callback, and change `pending` to `ready` with no pending reason once
   the implementation is runnable. Preserve existing IDs and avoid duplicates.
2. Verify `tools/run-tests e2e --list` reports the intended case as `ready` with
   the correct executable. This is the inventory `make test-all` already reads;
   every ready variant is automatically selected for its E2E stage. No per-case
   Makefile or launcher registration is needed.
3. Execute the whole scenario through its normal guarded selector and retain
   its result and cleanup evidence. `ready` means runnable, not passed. A failed
   run remains failed and cannot earn completed customer coverage.

Use the inventory listing to verify inclusion and the focused run to verify
behavior. This adds no per-scenario full `make test-all` run or new registration
infrastructure; existing task and aggregate acceptance checks still apply.

## Completion must be demonstrated by the current run

A variant passes only after all declared customer actions and visible assertions
execute, evidence is retained safely and existing cleanup succeeds. Listings,
registrations, helper passes, partial journeys and revised plans are not
completed scenarios. Preserve first failures; later passes have distinct runs.

Claim implementation complete only when the passing scenario is also registered
and confirmed discoverable under the rule above. A documentation checkbox or a
test file absent from the runtime inventory cannot satisfy completion.

Report completed/remaining customer variants, scope additions/transfers,
demonstrated product blockers and infrastructure blockers separately.
Reclassifying an internal assertion never counts as a passing journey.
Mechanical package qualification keeps its own finish lines and evidence;
a customer-suite pass does not certify product internals.
