# 001a — Confirm the live-time observation contract

Acceptance: review

Required tasks: 001, 001a0.
Estimate: 20–30 minutes; one bounded contract decision for both supported systems.

## Purpose and scope

Pin the existing public inputs and the live-observation composition selected by
[001a0](001a0-live-time-support.md), under the
[row 4 exploration](../SystemDesign/Replace-Main.timeLimitsManager.md). Confirm
that the documented semantics can support the proposed finite consumer scope
on both `onpc-Ubuntu26.04` and `onpc-Fedora44`. This is a contract decision,
not a reader implementation or installed timing acceptance.

The current helper reaches `NativeTime1.GetDeadline` in the extension. Completed
Malcontent usage records omit uninterrupted activity; a fresh estimate based
only on those records cannot establish an independent live deadline. Reuse
task 002's investigation instead of repeating the same unsuccessful fallback.

Awaiting the revised 001a0 exploration, not delivery of a new native API. The
old direct-reader finding is retained: neither completed records nor fresh
`GetEstimatedTimes` alone supplies live use. A supported combination may be
evaluated, but missing startup/recovery input remains a blocker. Upstream work,
native replacement and a second durable usage ledger are forbidden.

## Reading and decision

Start at the [master's prerequisite plan](../Broker-Expiry-Plan.md#native-time-prerequisite-plan),
[Screen time](../SystemDesign/Screen-Time.md#grant-arithmetic-and-usage-identities),
[State](../SystemDesign/State.md#persistent-and-derived-state),
[Broker trust boundaries](../SystemDesign/Broker.md#runtime-hierarchy-and-trust-boundaries)
and [expiry design](../SystemDesign/Broker-Expiry-Locking.md#existing-automation-and-missing-acceptance).
Follow [source discovery](../Approval-Tools.md#source-discovery-before-reads).
The known call chain is in:

- [core.py](../../broker/oh_no_parent_control/core.py): status, fixed approval,
  `_native_deadline` and `_time_status_from_usage`.
- [adapters.py](../../broker/oh_no_parent_control/adapters.py): `TimerUsage` and
  exact-child helper execution.
- [usage helper](../../broker/oh-no-parent-control-query-usage): `--native-deadline`.
- [extension export](../../child/applicationUi.js): `NativeTime1.GetDeadline`.

Inspect official contracts/source and the applicable versions for the selected
logind/Malcontent inputs, using Mutter only if the exploration establishes a
specific need. Pin semantics, credentials, account/session scope, units,
precision, clock domain, lifecycle and bounded failure behavior. Specify how
initial state/history acquisition, observed unfinished activity and newly saved
intervals reconcile without omission or overlap double counting. Distinguish
the daily operand from an effective endpoint that already includes a grant.
Pin how delay consumes the original deadline and stale/incomplete input refuses.
API existence or introspection alone proves no live-use claim.

Logind observations may support the explicitly reviewed transient live interval;
they are not proof of secure lock completion or a history of missed transitions.
Do not poll static estimates into a second ledger, submit usage checkpoints,
scrape a GUI/private state, evaluate Shell JavaScript or re-export the disabled
extension endpoint. No product edits, observer implementation, installation,
expiry scheduler or new daemon belongs to this decision. Native recording and
Malcontent storage remain unchanged. Do not invent a public live-balance API.

## Expected result and cleanup

Record the selected input contracts, official documentation, version facts and
remaining integration gates in the row 4 exploration and 001b's existing brief.
Keep 001b deferred until its concrete implementation scope is explicitly ready;
passing this review does not activate it. Use a short queue
note; create no evidence archive and add no tests of plan documents. Apply the
[test scope mandate](../Mandates/Test-Scope-Mandate.md) to any proposed product
coverage, and check changed Markdown links.

Pass only when the proposed composition has a concrete, supportable contract on
both systems with no unresolved correctness choice hidden in implementation.
Name how native history and observed activity establish the start/recovery state;
otherwise leave this row unchecked with the exact missing input and return
condition. Do not pass with a hypothetical API, an unsupported finding, or a
proposal to change native packages. The current product remains on its working
path; 001b must not guess an implementation or weaken task 002's assertions.

Use [approved read routes](../Approval-Tools.md) for research. Read the
[VM mandate](../Mandates/VM-Mandate.MD) before any necessary guest inspection;
use maintained non-graphical inspection routes, not another workflow launcher.
Finish owned inspection/session cleanup before returning. No installed result
for task 002 is earned here.
