# Broker countdown and extension display

Status: Session 1 complete; Session 2 focused installed countdown, recovery and
older-release upgrade checks passed on both VMs. Whole-product release readiness
is blocked by unrelated host-test failures and incomplete release checks. Rows 1
and 2 are implemented together; the increment is not yet accepted as shippable.
This is a bounded migration step, with the extension still required.

## Outcome and release boundary

Move the child panel's product deadline calculation into the existing broker.
The extension supplies its existing native timing observations, receives an
absolute deadline, and renders the countdown locally. It no longer selects the
timing operand or reconstructs entitlement from a returned duration.

This increment can ship with the extension still required. Global extension
disablement remains an unresolved product dependency. Do not claim that timing
or enforcement works independently of the extension after this change.

The endpoint is a working, validated product with this migration step complete,
not a partially connected broker API or an extension awaiting integration.
Rows 3 and 4 are not release prerequisites for this increment. Shippable means
the acceptance below and the applicable [release preparation](../Publishing.md)
and [upgrade acceptance](../Publishing.md#upgrade-acceptance) are complete, with
no unresolved release blockers. Documentation completion alone establishes none
of those results. Actual publication remains a separate authorized action.

| Row | Responsibility | Scope of this increment |
| --- | --- | --- |
| 1 | Move countdown arithmetic into broker | Implemented; focused installed checks passed; release readiness blocked |
| 2 | Make extension display broker results | Implemented with row 1; focused installed checks passed; release readiness blocked |
| 3 | Schedule broker expiry and invalidate it after policy changes | Excluded; retain existing expiry owners |
| 4 | Replace access to `Main.timeLimitsManager` | Excluded; retain existing native timing inputs |

Rows 3 and 4 are distinct work, but their final independence claim is shared.
Row 3 can initially use extension-backed timing; that would still depend on the
extension. Row 4 can deliver an independent timing source without moving expiry
ownership. Extension-independent broker expiry requires both. Neither is a
prerequisite for this increment, and neither may be implemented here.

Upstream changes are forbidden. Keep GNOME/Malcontent recording and Malcontent's
usage store. [Replace Main.timeLimitsManager](Replace-Main.timeLimitsManager.md)
owns the separate row 4 exploration. The superseded upstream/package
[support proposal](../Live-Time-Support-Plan.md) is not an authorized route or
a prerequisite for this increment. Do not implement the timing exploration,
change its queue, or mark its source/reader tasks complete through this work.

## Two-session boundary

These are session boundaries within one increment, not separate deliverables or
a formal execution plan. Keep the broker and extension changes together. Do not
add a task queue or launcher. Two sessions are the intended allocation, not
permission to omit checks or declare unfinished work shippable.

### Session 1 — Implement the complete change and verify locally

Implement rows 1 and 2 together, including refresh, failure and grant-confirmation
behavior specified below. Complete the host tests, independent backend review,
package build and documentation checks in [close-out](#acceptance-and-implementation-close-out).
Update current design descriptions, leaving installed acceptance pending.

Stop before installed VM acceptance and release preparation. The boundary is
complete only when the broker and extension work together, affected host checks,
review and package build pass, and changed Markdown links pass. Leave a short
handoff in this document identifying changed behavior, completed checks, the
candidate packages and exact remaining installed/release checks or blockers.
Do not describe the increment as accepted or shippable at this boundary.

### Session 2 — Verify the installed product and finish release readiness

Resume the handoff without rerunning unchanged completed checks just to prove
them again. Finalize release inputs through the existing release-preparation
workflow before validating the final candidate. Complete the required local
release checks, affected installed acceptance below on both named VMs, and the
supported previous-release upgrade under the existing upgrade contract,
including retained settings and the activation required by the actual package
manifest comparison. Scoped
countdown checks alone do not establish whole-product release readiness.

Fix only issues within this increment. Later source or release-input changes
receive the affected review, build and validation under the existing contracts,
so the candidate intended to ship is the candidate tested. Preserve completed
unchanged checks. Apply the stopping rule below to excluded dependencies and
report unrelated release failures without broadening this assignment.

Complete [close-out](#acceptance-and-implementation-close-out) and record a short
final result here: both VM outcomes,
upgrade/activation and release-readiness results, and any precise remaining
blocker. Mark the increment complete and shippable only when all required checks
pass and no release blocker remains. The release description must state that
the extension is still required. Do not publish or implement rows 3 and 4.

## Existing code and reading route

Read [Screen time](Screen-Time.md#grant-arithmetic-and-usage-identities),
[countdown and expiry](Screen-Time.md#countdown-and-expiry-enforcement),
[broker trust](Broker.md#runtime-hierarchy-and-trust-boundaries),
[state ownership](State.md#persistent-and-derived-state) and
[package activation](Lifecycle.md#package-activation-and-session-renewal).
Expected customer behavior remains in the [specification](../Specification.md).

Read complete affected functions and their necessary callers before editing:

- [remainingTimeIndicator.js](../../child/remainingTimeIndicator.js):
  `_refreshEstimate`, `_schedule`, `_sync`, `showGrantedTime` and disposal.
- [indicatorLogic.mjs](../../child/indicatorLogic.mjs):
  local subtraction, formatting and display helpers; source selection and
  duration-to-deadline reconstruction have been removed.
- [timeCalculationClient.js](../../child/timeCalculationClient.js) and
  [timerQuery.js](../../child/timerQuery.js): existing asynchronous transport,
  native estimate acquisition and bounded error handling.
- [core.py](../../broker/oh_no_parent_control/core.py):
  `calculate_own_deadline`, its clock samples and the compatible
  `calculate_own_remaining_time` formula; distinguish these from `get_time_status`
  and approval-time calculations.
- [service.py](../../broker/oh_no_parent_control/service.py) and the
  [published D-Bus contract](../../data/dbus-1/com.puffyslippers.OhNoParentControl1.xml):
  method declarations, caller identity, dispatch and errors.

The broker now selects the native/fallback endpoint and combines it with its
live AccountsService grant. The extension consumes the absolute monotonic
deadline and refreshes on existing notifications rather than display ticks.
Keep this path narrow; do not redesign the rest of time management.
Preserve all pre-existing checkout changes, including pending native-time tests.

## Bounded implementation

Keep the existing push flow: extension samples native timing, asynchronously
calls the broker, and consumes its result. No new broker-side helper reads,
activity observers, background workers, subscriptions or persistent state are
needed for the calculation itself.

`CalculateOwnDeadline(native_deadline_realtime_usec, timer_deadline_realtime_usec)`
is the child-scoped calculation method alongside the compatible existing API.
It takes raw absolute realtime-microsecond endpoints (zero means absent).
The broker selects the operand using the current rule, reads the caller's live
grant, and returns one absolute monotonic-microsecond deadline. Values must be
safe integers for GJS. No caller-selected target or grant is accepted.

The calculation contract is:

1. Derive the child from D-Bus credentials, validate the same managed-child role,
   and validate all timing inputs. Never accept a caller-selected grant or
   target identity. A child-provided observation retains its current trust level;
   it does not authorize policy writes or establish extension independence.
2. Preserve the existing native-endpoint preference, including an expired
   positive native endpoint. Preserve the existing inactive/no-native-endpoint
   timer fallback; distinguish it from a failed source read. Fresh completed-use
   estimates must not override a binding native endpoint during continuous use.
   Do not switch the panel to `GetTimeStatus` as an assumed equivalent.
3. Combine the selected timing operand with the broker-read live grant using
   the existing maximum rule. Do not infer an exact grant-free daily balance
   from GNOME's effective endpoint or change approval arithmetic.
4. Convert the absolute source/grant endpoints with bracketed realtime and
   monotonic samples. Transport and calculation latency consume the original
   interval; never restart a returned duration at receipt. Round for display
   once, and reject an unprovable clock mapping through normal error handling.
5. The extension stores the returned deadline directly. Local subtraction,
   formatting, animations and reminders remain presentation work. Existing
   expiry code may use that deadline; its lock ownership is unchanged.

Keep the extension's native timing export independent of this calculated result.
It must still read GNOME directly, not call back into the broker or read the
panel's cached product deadline. Do not modify the fixed usage helper/native
reader to make this refactor work.

## Refresh and failure behavior

The local display tick must not call the broker or query Malcontent every second.
Refresh the calculation on initial load and relevant existing timing, limit,
grant, approval/revocation, inactivity/resume and clock changes. Reuse the current
native notifications and lifecycle hooks; do not build a general event framework.
Verify that these notifications cover the removal of tick-driven refreshes.
If a concrete gap requires an additional notification, use only the smallest
product-specific invalidation and document its trigger; it grants no background
expiry scheduling scope.

Coalesce refreshes using the current pending/again mechanism. Preserve disposal
guards and reject late replies invalidated by a newer policy/source change.
Broker owner replacement invalidates outstanding work and requires a fresh read.
Retain the last verified deadline through transient failures without extending
it; use bounded recovery retries, not permanent per-second polling. A failed
first read is unavailable, not a loaded zero balance.

Any grant-confirmation path touched by this change must consume a broker-issued
deadline or request a fresh calculation. It must not award the original grant
duration again from confirmation/receipt time. Keep the existing live-grant
authority, unavailable-state reporting and unchanged policy write paths.

## Hard exclusions and stopping rule

Do not add a broker expiry scheduler, move lock requests, remove resume/unlock
workarounds or session preparation, change extension activation/readiness, or
make the entire extension presentation-only. Row 2 concerns its countdown
calculation consumer only. Keep native recording, existing extension lock guards
and the native timing bridge operational.

Do not add logind/Mutter activity tracking, a live-interval ledger, usage
checkpoints, storage/schema migration, another daemon, upstream patches or native
package replacements. Do not migrate Parent/kiosk status, approval formulas,
PAM/admission or account-wide accounting. No new launcher, task queue, provider
qualification campaign or unrelated test repair belongs here.

If completing the increment requires any excluded change, leave the working
production path intact and report that precise dependency. Do not enlarge the
assignment or weaken acceptance to force completion.

## Acceptance and implementation close-out

Follow the [test documentation map](../TestAutomation/README.md) and
[test scope mandate](../Mandates/Test-Scope-Mandate.md). Reuse existing owners:
[core](../../tests/unit/test_core.py),
[service contract](../../tests/unit/test_service_contract.py),
[private D-Bus component](../../tests/component/test_private_dbus_service.py),
[indicator logic](../../tests/child/indicator_logic.test.mjs) and
[GJS adapters](../../tests/child/gjs_adapters_test.js). Add only missing product
assertions for this increment, not tests of this document or ordinary helpers.

Acceptance is finite:

- Broker-owned endpoint selection/live-grant combination and caller refusal;
  unchanged daily-only, grant-only and combined semantics.
- One original deadline survives delayed replies and repeated display ticks;
  local ticks make no broker calls. Invalidation refreshes it without accepting
  stale replies. Source/broker failures retain or refuse state as specified above.
- Existing countdown/reminder presentation, approval/revocation refresh,
  lock/unlock or inactivity return, and natural expiry still work. A shorter
  expired/revoked grant preserves positive daily time.

Run the lowest effective maintained host selections in Session 1, then affected
installed checks on `onpc-Ubuntu26.04` and `onpc-Fedora44` in Session 2. Reuse the
existing countdown cases 27–29 and affected expiry/recovery owners; do not create
another scenario matrix or rerun completed unrelated tasks. Use
[test maintenance](../../tests/README.md#all-established-regressions) and launcher
help/listing to select actual registered checks. Read the VM/UI/storage mandates
before the respective operations, retain existing finite timing inputs and
finish owned cleanup. Installation uses only the maintained guest workflow and
`make install`, never installation on the development host.

Core backend implementation retains the model/effort and independent Astra xHigh
review required by [AGENTS.md](../../AGENTS.md#product-boundaries). Build packaged
changes with `tools/build_package.py` after the final such edit; apply the existing
[activation rules](../Publishing.md#package-update-activation) to broker and
extension updates. Update the affected current design descriptions, check changed
Markdown links, and leave the session handoff or final result specified above.
Release preparation is in scope for Session 2; publication is not authorized
here. Passing this increment earns no row 3/4 or extension-disabled acceptance.

## Session 1 result

Session 1 completed on 2026-11-01. The broker selects the native/fallback endpoint
and live grant; the extension stores its absolute deadline, rejects stale
replies, retries failed reads finitely and renders locally. Existing native
notifications cover grant, policy, activity and clock invalidation. Lock owners,
resume workarounds and the independent native export remain in place.

Focused validation passed: 883 unit tests across `test_core.py`,
`test_service_contract.py`, `test_diagnostics.py` and `test_diagnostic_privacy.py`;
18 private-D-Bus component tests; the indicator, diagnostic and notification
Node selections; GJS adapter tests; JavaScript static checks; and changed Markdown
links. Astra xHigh independently reviewed and revised the production change:
uncertain clock samples now fail rather than expire time prematurely. Its
requested expired-native/live-grant combination also passed its affected core
test. No remaining blocking host-review findings were identified.

`tools/build_package.py` completed both formats after the final packaged edit:
`output/deb/oh-no-parent-control_2.0+local1~ubuntu26.04.1_amd64.deb` and
`output/rpm/oh-no-parent-control-2.0-0.1.dev.fc44.x86_64.rpm`.

## Session 2 result — 2026-11-01

Finalized the v2.0 release date and notes, retaining the extension requirement.
Both package formats built and clean DEB/RPM publishing checks passed.

| Installed check | Ubuntu 26.04 | Fedora 44 |
| --- | --- | --- |
| Countdown cases 27–29: daily-only, grant-only, combined | Passed | Passed |
| Graphical expiry/recovery 282: locking, retained work, peer session, PAM and extension recovery | Passed | Passed |
| Older-release upgrade 287: retained settings, migration, readiness, grant preservation, enforcement and reboot activation | v1.2 → v2.0 passed | v1.3 → v2.0 passed |

Old and current product packages were built locally from verified sources.
All owned cleanup and baseline restoration completed. Nothing was published.
Pending journeys in the existing
[coverage allocation](../TestAutomation/UI-and-E2E-Coverage.md#expiry-locking-migration-allocation)
remain pending; these results do not extend their acceptance.

### Remaining work

1. Repair the two failures in `test_desktop_language_cleanup_safety.py`:
   `test_guest_valid_api_input_and_invalid_declared_bindings` hit
   `session:fixture-identity`; the `[api-error]` variant of
   `test_guest_refuses_before_mutation_or_never_retries_uncertain_api` expected
   one language write but observed none. A test-fixture defect is suspected;
   the cause is unconfirmed, with no evidence linking it to this migration.
   Use `tools/fix-tests unit 'tests/unit/test_desktop_language_cleanup_safety.py' -q`.
2. Resume incomplete normal release checks with `tools/run-tests --resume host`
   after repair, preserving completed unchanged selections. The full host run
   stopped at those failures; interrupted and unstarted checks are not passes.
3. Determine activation for the supported release-to-candidate transition from
   the actual [package manifests](../Publishing.md#package-update-activation).
   Check 287 qualifies the tested reboot transitions. Separate no-reboot
   acceptance is required only if the intended transition requires broker
   restart/session renewal rather than reboot; then verify retained settings,
   broker restart, child logout/login and working countdown/enforcement without
   reboot. Applicability has not been established; no activation defect was observed.

The increment remains unshippable until these release gates close. Preserve the
completed checks; later source changes receive only their affected validation.
