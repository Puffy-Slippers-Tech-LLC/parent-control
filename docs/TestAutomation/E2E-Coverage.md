# Real end-to-end operations and scenario coverage

This is a required planning and acceptance contract for unfinished automation
tasks. It describes future work; an entry below is not evidence that a test has
been implemented or passed. The [master plan](Test-Automation.md) owns task
order; the [daily guide](../Test-Automation.md) owns the public command interface.

## Scope tests around the app

Every expensive test must name the app behavior, app-owned OS integration, or
necessary harness safety guarantee it protects. Record the regression it would
catch and the lowest layer that can establish that result. Test-count growth,
upstream functionality and the availability of an automation API are not reasons
to add a product scenario.

| Boundary | Required focus |
| --- | --- |
| Product behavior | Policy, grants, expiry, discovery, approvals, request surfaces, isolation, persistence and package lifecycle. |
| App-owned OS integration | The app's PAM/Polkit wiring, service ordering, execution rules and their effects on real users/processes. |
| Unrelated prerequisites | Establish real accounts, roles, application assets and input files through reliable supported helpers; verify the resulting state. |
| Harness safety | Owned cleanup, correct prompt targeting, secret exclusion, input integrity and failure reporting; keep qualification distinct from product coverage. |

Do not build matrices for Ubuntu's password verifier, Users settings UI, package
manager internals, third-party game correctness or delivery-provider reliability.
Their app-facing integration boundaries still need focused evidence. For example,
correct-password login/unlock denial at zero time is essential. Ordinary
wrong-password login needs at most one focused regression of our modified PAM
stack; it is not a password-policy matrix. Wrong-password or cancelled **app
approval** must prove no grant/policy change, preserved choices and successful
retry on each request surface. Wrong-prompt refusal qualifies secret input; it
does not establish an application authentication outcome.

## Prepare prerequisites through supported helpers

Separate fixture setup from the actions and causal transitions the test claims
to prove. Choose the simplest reliable existing CLI/API/helper, prefer verified
local assets, and reuse it across cases. A prerequisite does not need a GUI
workflow merely because a customer could create it that way.

- Create real account/role fixtures through supported guest OS tools or public
  AccountsService APIs. For dynamic discovery, keep Parent running, create the
  account through the fixture helper at a recorded boundary, verify its real
  eligibility, and observe Parent discover/select it without restarting. Account
  creation is a fixture event; Parent's response is the tested behavior.
- Stage fixture apps, a pinned offline game, synthetic attachments and input
  data directly through verified asset/provisioning helpers. Install the product
  with the real package manager during setup when installation is not the tested
  transition. Keep the product absent at the start of clean-install tests.
- Initial product configuration may use a maintained public product interface
  when that configuration transition is outside the test's claim. Record the
  setup and independently verify the state. Authorization still applies; grants
  must result from a real authorized approval. Never write private product
  records, forge grants/authentication, or use a production test hook. Approval,
  save, revocation and persistence journeys retain their actual UI operations.
- Provision only within the existing guarded attempt. Host dependency changes
  still go through `setup.sh`; no new VM, baseline or in-journey restore is
  permitted. Use bounded readiness checks, recorded fixture ownership and safe
  cleanup. A failed prerequisite stops dependent execution; distinguish product
  and infrastructure causes and never pass unexecuted product assertions.
- Record the helper, input identities, timing and verified pre/postconditions.
  A normal prerequisite event during a test is not a fault injection. Keep its
  write capability separate from read-only observations and declared faults;
  it cannot perform the outcome the test is asserting.

Use only implemented validated runner capabilities. If a required fixture event
is not representable in today's inventory/controller, the owning task must add
the smallest supported provisioning contract and its focused safety checks
before execution. Do not label a helper write as UI input/read-only evidence or
open an unrestricted guest-command route. No setup shortcut may replace a step
in E2E-023 or another explicitly continuous product journey.

## Customer journeys must exercise the real machine

A customer E2E scenario is an uninterrupted sequence of actions on the real
installed product and operating system in the guarded test VM. Automation sends
keyboard and mouse input to the guest display through a maintained public
automation backend, observes the screens, and performs the same operations an
end user would perform manually. Virtual hardware is the test environment;
product behavior and operating-system enforcement must be real.

- Install the digest-identified Debian package. Use real GDM, GNOME sessions,
  system D-Bus, broker, AccountsService, Malcontent, PAM, Polkit, fapolicyd, and
  installed application processes. No preview mode, fake service, stubbed
  reply, patched authorization, or test-only production path may participate.
- Perform the login, Switch User, logout, settings, request, password, approval,
  revocation, launch and restart operations asserted by the journey through the
  customer's real interfaces. A tested command-line customer operation, such as
  APT installation in the package journey, is entered in the guest terminal with
  real authorization. Unrelated setup follows the prerequisite rules above.
- Enter credentials only into the real login/authentication prompt using
  secret-safe input. A helper calling the broker, approving Polkit, setting a
  grant, or changing preferences cannot stand in for a customer action.
- Grant expiry and daily-allowance consumption use real measured usage and
  elapsed time. Use short supported durations selected through the UI. Never
  write usage/grant state, jump the clock, invoke Lock, or patch a timer to
  manufacture the outcome of a customer expiry scenario.
- Preserve causality: each step consumes the state produced by the preceding
  actions. Reboot really reboots; user switching retains the actual sessions;
  package operations execute real maintainer scripts. Do not reconstruct the
  expected state behind the UI between steps.
- No VM snapshot creation, save-state/load-state, checkpoint restore, cloned
  installed image, or step-resume shortcut may construct or resume a journey.
  In particular, never restore a snapshot to simulate login, grant, expiry,
  reboot, recovery, installation, or removal. A failed attempt remains failed;
  any diagnostic rerun starts the entire scenario again.
- The already-approved product-free baseline is only an outer
  preparation/cleanup boundary between independent attempts on the same VM.
  Preserve it; create no additional VM snapshots or disposable overlays. Once
  a journey starts, no baseline restore occurs until that attempt has ended
  and its evidence has been collected. Tests may not restore between the
  steps of an install/upgrade/remove/reinstall or cross-user journey.
- Provisioning test accounts, package assets, and declared third-party apps
  before the journey is permitted. Product configuration or authentication
  that the journey claims to test must be performed in its visible steps,
  rather than hidden in provisioning. Record all preconditions explicitly.
- Read-only guest assertions may corroborate screens with grants, usage,
  sessions, installed files, policy, and process identity. They must not drive
  the tested outcome or disturb the foreground session. A backend assertion
  cannot replace a visible success, denial, lock, or return-to-GDM assertion.

Customer-error journeys exercise the app's response to representative invalid
input, rejected/cancelled approval, duplicate submission and denied access using
real UI and services. Assert product state and recovery, not only an upstream
error message. Exhaustive local validation cases do not each require a new
complete graphical journey.

## Distinguish supporting tests without weakening E2E

Host unit and component tests may isolate dependencies with mocks. They remain
part of the local regression suite, but cannot provide customer E2E evidence.
Guarded installed-system tests exercise real OS interfaces directly and remain
required even when they are not keyboard-and-mouse journeys.

Graphical fault/recovery scenarios may deliberately stop a real service,
change an account's real eligibility, or trigger a supported OS failure. Declare
each such intervention, its actor, and the evidence that the fault occurred;
classify the scenario as `fault-recovery`. Do not substitute fake product
services or responses. Controlled guest date/time tests are similarly labeled
`environment-boundary`; they do not prove natural elapsed-time behavior.
Ordinary UI behavior before and after an intervention must still be real.

Runner smoke, process fixtures, fault injection, and controlled-time results
must not be relabeled as normal customer journeys. All required categories are
included by default in `make test-e2e` or `make test-system` as appropriate, and
in `make test-all`; separate labels describe the evidence, not optional scope.

Tiny native/Snap/Flatpak fixtures provide deterministic real launch and process
identities. They are useful for policy matrices but are not evidence of playing
a customer game. Gameplay journeys additionally require a real, version-pinned
installed game with a reproducible offline level or session, entered through
its normal UI. Verify gameplay and input, including windowed and fullscreen
expiry cases. Record its package/runtime identity and asset digests; a menu,
sleeping process, or substitute test window is not gameplay evidence.

## Enumerate scenarios before implementing them

Include installed surfaces outside the original policy examples, such as
About/license access and feedback drafting, validation, attachment review,
cancel and retry. Declare external delivery separately: it needs the actual
supported service, explicit authorization and a dedicated test recipient.
Do not send routine automation to the production support inbox or present fake
transport results as delivery evidence. The inventory must state the tested
service boundary and required profile; missing prerequisites for a required
delivery case block its acceptance rather than silently substituting a mock.

Task 19A has established `tests/e2e/scenarios.json` as the executable scenario
inventory. Each later E2E task audits and implements its assigned entries,
expanding only missing obligations rather than reconstructing the inventory.
The [inventory validator and selection interface](../../tests/e2e/README.md)
now enumerate the starting cases, all explicitly pending. E2E-030–033 also
record About/license, feedback draft/review, authorized delivery and declared
transport-failure retry obligations omitted from the table below. Their missing
normative requirement links remain explicit gaps for the owning tasks.
The inventory must contain stable scenario and variant IDs, category,
responsible task, requirement IDs, affected components, supported environment,
explicit preconditions, ordered customer actions, declared interventions,
visible/backend/other-user assertions, executable test IDs, expected evidence,
and bounded duration. Record setup, start, steps, end, and cleanup separately.

Use the [implementation workflow](Implementation-Workflow.md) to prove a helper
before expanding its cases, and to retain small handoffs between solved
problems. Task verification is acceptance scope, not an instruction to run all
journeys after every edit.

The table below is a required starting inventory, not the complete coverage
claim. Expand each family into individually selectable cases before its task
is accepted. Preserve IDs when wording changes. Task 26C closes missing
continuous journeys; Task 28B audits the complete executed inventory.

| Scenario family | Owner | Required journey or outcome |
| --- | --- | --- |
| E2E-001 | 19B/19A | Real boot, stable GDM/prompt/return matching, public controller preparation, credential/asset forwarding, serial command, boot continuity and terminal evidence/cleanup; category `runner-smoke`. Supersedes the duplicate E2E-034/serial-controller qualification; its historical acceptance evidence remains under Task 19A. |
| E2E-002 | 20 | Product absent → real package installation → actual reboot → usable, enforcement-ready GDM. |
| E2E-003 | 21A | Parent login → app-grid launch → discover/select children; a supported fixture helper creates a real child while Parent stays open, then the UI discovers it. |
| E2E-004 | 21A | Standard user attempts Parent access; management remains unavailable. Direct D-Bus attacks are separately labeled installed-system evidence. |
| E2E-005 | 21A/21B | Parent changes allowance boundaries, toggles control, observes saving/loading and remaining-time state, then verifies actual child behavior. |
| E2E-006 | 21B | Parent edits allowed/hard/soft policy and exact/pattern matching → child attempts use → other user's applications remain usable. |
| E2E-007 | 21B/25B | Parent cancels revocation, then confirms revocation with apps open; check time, process, and other-session effects. |
| E2E-008 | 22A | Actual daily allowance is consumed → desktop locks without logout → correct-password zero-time unlock and fresh login are denied. |
| E2E-009 | 22A | Actual one-time grant expires → retained-session lock → new kiosk approval → successful unlock; cover both soft-app choices. |
| E2E-010 | 22A | Switch User while a grant expires; the other foreground user is uninterrupted and the child cannot resume without time. |
| E2E-011 | 22B | Real countdown passes minutes/final seconds; visibility is correct on unlocked desktop, lock screen, and GDM. |
| E2E-012 | 23A | Child panel → one overlay → select each eligible parent → real prompt → successful approval with and without soft apps. |
| E2E-013 | 23A/24B | Rejected/cancelled app approval preserves grants, policy and choices; successful retry commits once, on both request surfaces. |
| E2E-014 | 23B/24B | Both surfaces exercise predefined/custom/rest-of-day choices, fractional bounds, invalid values, and duplicate submission. |
| E2E-015 | 23B/24B | Cancel, Escape, and successful completion produce each surface's correct exit and countdown/selection behavior. |
| E2E-016 | 24A | GDM → restricted kiosk session; no general desktop or management access before or after a request. |
| E2E-017 | 24B | Kiosk switches children and approvers; empty/ineligible/disabled states prevent a request correctly. |
| E2E-018 | 24B | Change choices in one request surface → visit the other → verify per-child persistence and separately remembered mute. |
| E2E-019 | 25A | Parent-configured native/Snap/Flatpak rules are enforced through every supported launch route; positive and negative matches. |
| E2E-020 | 25A | App update or disappearance between display and save preserves the correct current target or saved rule. |
| E2E-021 | 25B | Real repeated logins/switches establish multiple users/sessions → save/approve/revoke → required child-only process effects. |
| E2E-022 | 26B | Configure and grant through the UI → actual app/session/machine restart or real idle/suspend/wake → resume use and verify time, persisted choices and enforcement. |
| E2E-023 | 26C | Parent sets zero allowance → Switch User → child denied → kiosk approval → child logs in and plays a real game → natural expiry → lock and unlock denial. |
| E2E-024 | 26C | Child requests additional time while time remains → real approval accumulates correctly → continued gameplay → eventual expiry. |
| E2E-025 | 26C | Expired grant → replacement grant before session entry, with each soft-app choice → correct policy and retained-app behavior. |
| E2E-026 | 26C | Parent configures → real package update → required process/session/reboot activation → customer logs in and uses preserved settings. |
| E2E-027 | 26C | Install → reboot → configure/use → remove → reboot → verify usable login → reinstall/use retained settings → purge. Task 18C supplies installed assertions. |
| E2E-028 | 20/22A/22B/24A | Real startup, zero-time desktop exposure, usage-read, and authentication-agent failures → visible safe denial/relock → real recovery; category `fault-recovery`. |
| E2E-029 | 21B/25B/26A | Real failed save, stale identity, disconnect, concurrent transaction, policy reload, and partial termination failures → visible rollback/safe state; category `fault-recovery`. |

Maximize meaningful coverage by tracing every applicable requirement and
customer-visible transition, not by stopping once these examples pass. Review
the [specification](../Specification.md), [system design](../System-Design.md),
[package activation](../Package-Update.md), [migration](../Data-Migration.md),
and [removal](../System-Design.md#package-removal-lifecycle) contracts. Add omitted
product behavior to the inventory and identify its authoritative requirement; do not silently omit
it because the original functional specification did not mention it.

## Bound the matrix before expanding it

Use thorough unit/property coverage for pure rules and meaningful boundaries,
component tests for form behavior and dependency outcomes, installed tests for
real OS integration, and focused graphical journeys for the wiring and causal
transitions that need a desktop. A lower layer cannot establish a required
graphical/security interaction, but an independent validation value need not
repeat an entire VM journey. Cover both shared-form modes at the local layer
and each surface's real approval, targeting, exit and persistence behavior.

Audit existing pending declarations before implementing them. Record each
variant's product risk, interacting dimensions and layer. Group compatible
values in one journey, reuse a canonical case, or move equivalent validation to
its effective layer with explicit requirement/case links. Reconcile the task,
scenario matrix and `tests/requirements.json` together; validate inventory and
stage traceability before execution. Preserve IDs for retained behavior and a
reviewable rationale for any superseded declaration. Do not hide required cases
with skips, mark them covered without execution, or silently weaken a specified
security, supported-route or continuous-journey requirement. Existing pending
entries remain pending until this reconciliation and their acceptance succeed.

For the current task, create a finite case/variant list tied to specification
IDs, required transitions and interacting dimensions. Reuse existing scenario
IDs and helpers; establish success, deliberate failure and one interaction
before filling that list. Keep all required pending cases visible. Record newly
discovered obligations with an owner and reason; block the current slice only
when they invalidate its tested boundary or prerequisite. Required omissions
still block their owning task and final acceptance. Do not invent new product
guarantees or continually expand presentation combinations without a requirement.

For each family, enumerate applicable dimensions: parent/child/kiosk and other
users; both shared-form surfaces; enabled/disabled control; zero/available/
expired/replacement time; daily-only/grant-only/combined time; allowed/hard/
soft apps; native/Snap/Flatpak and supported launch routes; new/retained/
locked sessions; windowed/fullscreen gameplay; approval/denial/cancel/failure;
and app/session/service/reboot/suspend/package lifecycle boundaries. Cover both sides
of validation boundaries and prove that other users remain unaffected.

Use explicit full combinations of the dimensions that interact at identity,
enforcement, grant-precedence or cross-surface boundaries. Do not multiply every
dimension across every scenario irrespective of an interaction. For independent
presentation dimensions, use boundary/equivalence cases or pairwise combinations
with a documented rationale, keeping every required value/transition represented.
No reduction may remove a specified security case, supported launch route,
request surface, other-user assertion, or required real customer operation.

Give each executable case one canonical owner. A continuous case may satisfy
several families/tasks when every required action/assertion is present; reference
that case instead of creating copies. Compatible validation values can be
exercised sequentially in one declared journey; different initial states and
interacting transactions still need explicit variants. Reuse code, not stale
evidence or hidden product-state setup. The full gate executes each required
canonical case once and validates all its requirement links.

Before accepting a task, reconcile family-level related owners with the actual
variant owners and required helper dependencies. If a complete pending journey
belongs to a later transaction task, explicitly correct its ownership and links
without dropping actions, assertions or IDs. Do not create a dependency cycle,
duplicate the journey for each task, or mark its early screens as a complete pass.
The [reuse review](Reuse-Map.md#resolve-before-the-affected-batch) records the
current E2E-005 split and requirement/prerequisite gaps to resolve.

A test count or blanket coverage percentage is not a completeness argument.
Missing required combinations remain pending and block final acceptance. Date, midnight,
and DST system cases from Task 16 remain required; do not claim those are
natural customer expiry runs when the guest clock was controlled.

## Required continuous example: E2E-023

Provision only the declared accounts, real game, and product package before
starting. Preserve the parent session when switching users. This entire list
is one scenario attempt, with no intermediate state injection or VM restore:

1. Log in as the parent through GDM and open Parent from the app grid.
2. Select the child, enable screen-time control, and set zero daily minutes.
   Verify the visible save and make the game usable under the selected policy.
3. Use the desktop's Switch User action. Attempt child login with the correct
   password; verify the time-limit explanation and absence of a child desktop.
4. Enter the kiosk from GDM. Select the child and approver, choose a short
   supported grant, and submit. Enter the approver's password only in the real
   system authentication prompt. Verify success and the normal return to GDM.
5. Log in as the child with the correct password. Verify the actual desktop and
   countdown, launch the real game through the app grid, enter gameplay, and
   interact with it. Run explicit windowed and fullscreen variants.
6. Let the actual grant expire while playing. Verify that the desktop locks
   and game input is inaccessible. Read-only evidence must show that the child
   session and game remain alive, and the parent/other users remain unaffected.
7. Attempt unlock with the correct password and verify zero-time denial.
   End the attempt, collect evidence, and only then perform guarded cleanup.

This example is a mandatory minimum, never the sole E2E acceptance scenario.

## Completion must be demonstrated by the current run

Join the scenario inventory and requirement mapping to collected test/variant
IDs, step outcomes, and the current run's evidence. Merely referencing an
existing test file, checking `covered`, or passing isolated fragments does not
prove a journey. Record real session/boot continuity across steps, declared
reboots and interventions, and any outer baseline operations. Capture enough
PII-safe screen/video and backend evidence to review the actual customer path.

`make test-all` must reconcile expected and executed suites, scenarios, and
variants, including harness/static checks without product requirement IDs.
Missing, skipped, expected-failing, interrupted, stale, flaky, or failed results
prevent success. Diagnostic reruns preserve the first failure. No restored
checkpoint or evidence from a different package/source/run may fill a gap.
