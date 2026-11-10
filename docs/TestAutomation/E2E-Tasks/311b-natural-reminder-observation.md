# 311b — Qualify natural reminder content and urgency

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **311a** — Saved fullscreen preference and shared reminder editing.
- **062** — Public preparation, real activity and natural expiry observation.
- **300i** — Installed overlay personal-language selection and normal return.

Estimate: 20–30 minutes. First planned consumer:
[task 311c](311c-fullscreen-reminder-visibility.md); final customer case:
[task 311](311-remaining-time-notifications.md).

## Scope and acceptance

Publicly save one Riley reminder at 30 seconds with literal `Save your game now`
and fullscreen enabled. Use the [finite reminder preparation](../E2E-Scenario-Recipes.md#explicit-time-preparation):
prepare assets and the public observer before the 10-minute real grant, then
require at least 300 seconds when arming the original countdown approach.
Perform real native activity until it naturally crosses that
threshold. Independently observe the owned ChildUI notification's exact literal
body, `critical` urgency and the current verified remaining seconds required by
the API contract, using elapsed bounds. Bind the saved row's trigger independently
from the public list; the emitted live balance is not that configured threshold.
Require no delivery before crossing; naturally exhaust access and require
the owned warning absent on the resulting lock. Qualify independent natural
delivery entry. Focused harness checks cover wrong account/endpoint, missing or
ambiguous surfaces, stale delivery and hidden/locked input; live observation
retains current ownership/lifetime guards without another settings/provider
qualification history. This slice supplies no fullscreen or translated-default
acceptance; task 311 owns those complete outcomes.

Ready the shared public notification observer before normal activity crosses
the threshold. Await the owned emission within its declared elapsed bound and
read body/urgency together from that current surface, rather than sleeping to
an exact second and taking one snapshot. Use the same observer through natural
lock to distinguish actual removal from lost observation. A missed transient
or observation gap supplies no absence/delivery result and cannot be repaired
by injecting a notification or resetting time.

## Shared implementation and gate

Use the [reminder qualification catalogue](../E2E-Building-Blocks.md#reminder-controls-and-notification-qualification)
for current slice readiness, reusable bindings and the canonical observation gap.

Extend shared facade/observation operations for ChildUI's
`child-time-notification`, `child-time-notification-message` and
`child-time-notification-urgency`. Read the actual emitted body and canonical
`critical|high` value, not a reconstructed expected notification. Reuse
`RemainingTimeNotifications.update` / `present` in
[remainingTimeNotifications.js](../../../child/remainingTimeNotifications.js)
and `GnomeApplicationUiAdapter.listSurfaces` / `elements` in
[gnomeApplicationUiAdapter.js](../../../child/gnomeApplicationUiAdapter.js).

The [public API owner](../Application-UI-API.md#child-panel) specifies current
verified remaining seconds for message `getValue`, matching `current.seconds`
in the adapter. `RemainingTimeNotifications.present` initializes it from the
current scheduled balance, and `update` replaces it with subsequent remaining
time. The shared facade already routes these IDs to the owned notification
surface, but the maintained natural-delivery observer and its installed
qualification remain missing. Return condition: implement that observer with
the saved threshold and emitted live balance distinguished and independently
compared; qualify natural crossing, current content/urgency and removal at lock.
The public notification surface and control IDs are stable across deliveries;
they do not expose a per-delivery identity. Establish an independent lifetime
binding before claiming the same warning survived a transition or was not
replaced. Extend the existing read-only ChildUI projection with a current-delivery
identity if needed, backed by the real owned notification lifetime, and qualify
the shared observer against replacement and stale reads. A stable surface ID
alone supplies no such proof. This is missing observation implementation under
the settled same-warning requirement, not a choice to relax that requirement.
Elapsed samples must not stand in for the saved threshold. Private clocks, injected reminders, preview
delivery and broker calls as UI input supply no acceptance.

Planned fixed selector: `check_e2e_natural_reminder_observation`; unregistered and
unqualified. Register before invoking
`tools/run-tests system check_e2e_natural_reminder_observation`.
Reuse unchanged countdown, reminder settings and natural-expiry qualification;
rerun only branches affected by the new public observation or guard.
