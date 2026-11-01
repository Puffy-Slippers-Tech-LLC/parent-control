# Broker countdown and extension display

Status: implementation handoff for a separate session; no implementation or
acceptance is delivered by this document. Implement rows 1 and 2 together as
one bounded increment. This is not a full optional-extension migration or a
new execution queue.

## Outcome and release boundary

Move the child panel's product deadline calculation into the existing broker.
The extension supplies its existing native timing observations, receives an
absolute deadline, and renders the countdown locally. It no longer selects the
timing operand or reconstructs entitlement from a returned duration.

This increment can ship with the extension still required. Global extension
disablement remains an unresolved product dependency. Do not claim that timing
or enforcement works independently of the extension after this change.

| Row | Responsibility | Scope of this increment |
| --- | --- | --- |
| 1 | Move countdown arithmetic into broker | Implement |
| 2 | Make extension display broker results | Implement with row 1 |
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
  `effectiveAllowanceRemaining`, `nextEstimateState` and display helpers.
- [timeCalculationClient.js](../../child/timeCalculationClient.js) and
  [timerQuery.js](../../child/timerQuery.js): existing asynchronous transport,
  native estimate acquisition and bounded error handling.
- [core.py](../../broker/oh_no_parent_control/core.py):
  `calculate_own_remaining_time` and its shared formula; distinguish these from
  `get_time_status` and approval-time calculations.
- [service.py](../../broker/oh_no_parent_control/service.py) and the
  [published D-Bus contract](../../data/dbus-1/com.puffyslippers.OhNoParentControl1.xml):
  method declarations, caller identity, dispatch and errors.

The broker already combines a caller-supplied remaining operand with its live
AccountsService grant. The extension currently chooses the native/fallback
operand, reconstructs an endpoint and refreshes the broker from its display
timer. Consolidate that narrow path; do not redesign the rest of time management.
Preserve all pre-existing checkout changes, including pending native-time tests.

## Bounded implementation

Keep the existing push flow: extension samples native timing, asynchronously
calls the broker, and consumes its result. No new broker-side helper reads,
activity observers, background workers, subscriptions or persistent state are
needed for the calculation itself.

Add the smallest child-scoped deadline calculation method alongside the current
API. It takes raw native and timer-fallback endpoints with explicit units and
clock domain, rather than an extension-calculated remaining duration. The broker
selects the operand using the current rule, reads the caller's live grant, and
returns an absolute monotonic-microsecond deadline. The exact method name and
minimal tuple are implementation choices; this is a planned interface, not an
existing callable. Keep existing methods compatible for unaffected callers.

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

Run the lowest effective maintained host selections, then affected installed
checks on `onpc-Ubuntu26.04` and `onpc-Fedora44`. Reuse the existing countdown
cases 27–29 and affected expiry/recovery owners; do not create another scenario
matrix or rerun completed unrelated tasks. Use
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
Markdown links, and leave a short result with remaining blockers. No release or
publication is authorized here. Passing this increment earns no row 3/4 or
extension-disabled acceptance.
