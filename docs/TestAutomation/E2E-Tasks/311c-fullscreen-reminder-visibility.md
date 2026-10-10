# 311c — Qualify owned reminder visibility during fullscreen play

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **311b** — Naturally emitted owned reminder body/urgency and public observation.
- **129** — Real offline-game fullscreen mode and usable activity.

Estimate: 20–30 minutes. First planned consumer:
[task 311](311-remaining-time-notifications.md).

## Scope and acceptance

Use the qualified real fullscreen game, with Riley's fixed literal 30-second
reminder and a short publicly prepared balance above that threshold. With the
saved fullscreen preference enabled, naturally cross the threshold and require
the owned banner's logical visibility independently of its `critical` urgency.
In a second independently entered interval, save fullscreen disabled, naturally
cross the same threshold while windowed and read `high` urgency, then enter the
same game's supported fullscreen mode while the warning remains current.
Require the same owned surface logically hidden, then visible again on normal
windowed return while its natural lifetime permits. Compare unchanged saved
reminder/policy values and usable activity; no private timer or notification
injection and no replacement fixture. Refuse wrong-child/banner ownership,
ambiguous/stale surfaces and unavailable fullscreen observations.

## Shared implementation

Use the [reminder qualification catalogue](../E2E-Building-Blocks.md#reminder-controls-and-notification-qualification)
for current slice readiness and reusable bindings.

The banner is repository-owned chrome, not a generic Shell message-tray
notification. Reuse the Application UI API's ChildUI
`child-time-notification` surface flags, whose `listSurfaces` / `elements`
mapping uses `current.card.visible` in
[gnomeApplicationUiAdapter.js](../../../child/gnomeApplicationUiAdapter.js).
Qualify that mapping to the owned renderer's normal fullscreen branch in
`showReminderBanner` / `createBanner` in
[reminderBanner.js](../../../child/reminderBanner.js); shared facade operations
must preserve current identity and hidden-input refusal. Observe suppression
through surface flags, without reading hidden elements or inferring it from
urgency alone. No external-provider selector, pixels, geometry or private actor
probe is authorized. Missing independent public visibility or fullscreen
identity retains a concrete qualification gate.

Planned fixed selector: `check_e2e_fullscreen_reminder_visibility`; unregistered
and unqualified. Register before invoking
`tools/run-tests integration check_e2e_fullscreen_reminder_visibility`.
Reuse unchanged fullscreen activity and natural reminder qualification; rerun
only affected bindings if their shared route or guard changes.
