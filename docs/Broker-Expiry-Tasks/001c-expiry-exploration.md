# 001c — Explore expiry coordination in the broker

Acceptance: review

Required tasks: 001.
Estimate: 20–30 minutes; one bounded row 3 source/design decision.

## Purpose and scope

Resolve the questions in [broker expiry locking](../SystemDesign/Broker-Expiry-Locking.md#bounded-exploration-and-result)
into a concrete native-versus-product recommendation. First establish whether
native GNOME covers the core obligation; a new broker scheduler is conditional
on a demonstrated gap. Keep the extension's convenience timing reader. This task
does not implement a scheduler, modify the service or run a live fault campaign.

Read the [master](../Broker-Expiry-Plan.md), expiry design and affected
Screen-Time/Broker/Lifecycle sections linked there. Discover and read the current
extension expiry callbacks, broker transaction/dispatch owners and service unit.
Reuse completed task 001 without inspecting old reports or rerunning its checks.
The completed [countdown design](../SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement)
is the current baseline, not implementation work in this launcher task.

## Required result

Update the row 3 exploration with the native-versus-product effect boundary,
deadline invalidation and pre-effect revalidation, completion observation and
bounded recovery design. Identify how management/authentication can avoid
blocking expiry and what protects a desktop during a broker/provider outage.
Do not promise that restart, a sent lock request or a hint proves input protection.
Separate current findings from required future installed qualification.

Name a finite native-qualification slice and, only if justified, a future broker
slice and its existing test owners, without activating delivery tasks. A finding
that no scheduler is needed is valid. Core extension-disabled qualification does
not require the convenience countdown or in-session overlay. Preserve the historical
revocation, retained-work, other-user isolation and no-logout requirements.

No upstream changes, native patches, new daemon, accounting replacement,
independent activity observer or extension removal belongs here. If an essential
effect/recovery choice cannot be resolved, retain its precise blocker. A design
recommendation supplies no scheduler or installed enforcement acceptance.

## Validation and close-out

Review the recommendation against the owning design/specification and existing
coverage allocation. Use read-only research and checkout reads; any necessary
guest inspection first follows the VM mandate and owns cleanup. No installation,
new tests, package build, VM fault run or new evidence archive is required by
this review. Check changed Markdown links and queue dependencies. Record only
the bounded review result and remaining gates; do not close deferred TA rows.
