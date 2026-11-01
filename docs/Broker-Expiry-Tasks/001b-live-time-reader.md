# 001b — Read live time without the extension

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: 001a.
Estimate: original reader-only estimate 45–75 minutes. Re-scope before activation
if the confirmed composition requires observer work; keep each indivisible
integration/review/packaging/cleanup boundary together on both targets.

## Purpose and scope

Scheduling: deferred. This retains the old reader delivery boundary and installed
acceptance; it is not an instruction to implement the proposed live observer.
The [row 4 exploration](../SystemDesign/Replace-Main.timeLimitsManager.md) and
[001a contract review](001a-live-time-source.md) must first identify a viable
composition of existing public inputs. If that needs more than a fixed-purpose
reader, revise this brief into finite adapter/observer work before explicitly
reactivating delivery. Passing the reviews does not activate this deferred row.
No upstream/native package changes or Malcontent replacement is permitted.

Source decision: no usable direct extension-independent live-time interface was
found in the versions below. That finding remains valid; it does not evaluate
the newly proposed logind/Malcontent composition. Its startup, overlap and recovery
decisions remain unresolved. This brief authorizes neither implementation against
the rejected estimate nor a speculative replacement accountant.

Read the [master's prerequisite plan](../Broker-Expiry-Plan.md#native-time-prerequisite-plan),
[Screen-time calculations](../SystemDesign/Screen-Time.md#grant-arithmetic-and-usage-identities),
[Broker trust boundaries](../SystemDesign/Broker.md#runtime-hierarchy-and-trust-boundaries)
and [state ownership](../SystemDesign/State.md#persistent-and-derived-state).
Follow the exact [source routes in 001a](001a-live-time-source.md#reading-and-decision)
and [source discovery](../Approval-Tools.md#source-discovery-before-reads).
Read full affected functions and necessary callers before editing.

Keep the change at the existing native reader boundary where possible. Preserve
exact-child identity, bounded helper calls and output validation. Consume the
source's clock/precision contract without extending time during transport or
repeated reads. Preserve the live AccountsService grant and all existing daily
versus grant arithmetic and authorization. Refuse unavailable, malformed, stale
or wrongly scoped input; never substitute zero use or cached entitlement.
If the confirmed source cannot fit these requirements, stop and resolve that
specific boundary rather than silently changing the product contract.

No second durable ledger, synthetic usage records, policy/grant-store changes, private
Shell access, GUI scraping, new daemon, expiry scheduler, locking changes or
removal of extension responsibilities belongs here. Retain the working extension
production path until the affected independent integration passes. Update the
owning design and package activation contract for the actual reader change.

## Source review and return condition

The 2026-11-01 review used upstream interface documentation and implementation,
plus published distribution package versions. It did not start either VM or
claim a fresh inspection of installed packages.

| Target | Published package versions reviewed |
| --- | --- |
| `onpc-Ubuntu26.04` | [Malcontent 0.14.0-0ubuntu1.2](https://packages.ubuntu.com/resolute-updates/malcontent), [Shell 50.1-0ubuntu1.4](https://packages.ubuntu.com/resolute-updates/gnome-shell) |
| `onpc-Fedora44` | [Malcontent 0.14.0-1.fc44](https://packages.fedoraproject.org/pkgs/malcontent/malcontent/fedora-44.html), [Shell 50.6-1.fc44](https://packages.fedoraproject.org/pkgs/gnome-shell/gnome-shell/) |

The public candidate is system-bus name `org.freedesktop.MalcontentTimer1`,
path `/org/freedesktop/MalcontentTimer1`, interface
`org.freedesktop.MalcontentTimer1.Child`,
`GetEstimatedTimes('login-session') -> (ta{s(btttt)})`.
The [official interface contract](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/org.freedesktop.MalcontentTimer1.Child.xml)
returns the daemon's evaluation time and an optional empty-string entry containing
exhaustion, current-session start/end and next-session start/end. Timestamps are
Unix wall-clock seconds, with whole-second precision, not monotonic microseconds.
An absent entry means no applicable limit, not zero remaining time.

The [implementation](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/child-timer-service.c#L1137)
derives the account from the calling bus connection's Unix credentials and NSS;
UID 0 and unknown users are rejected. It accepts no selected UID or graphical
session ID. The `login-session` estimate is account-scoped. Identity, disabled
recording, policy, storage and busy failures return errors. The daemon may exit
on inactivity; activating a new owner does not restore unsent Shell activity.
`EstimatedTimesChanged` carries no data or freshness witness.

This candidate is rejected because its calculation reads saved usage totals and
adds the resulting remaining time to the current wall time. Shell explicitly
[documents why the unfinished active interval is absent](https://github.com/GNOME/gnome-shell/blob/50.1/js/misc/timeLimitsManager.js#L280-L296).
Repeated fresh calls during uninterrupted activity can therefore move the daily
expiry forward. This is missing accounting input, not transport latency.
The official [command-line reader](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/malcontent-client/malcontent-client.py#L932)
`malcontent-client get-estimated-times login-session` invokes the same method.
`QueryUsage` returns recorded intervals; neither route fills that gap.
The [library calculation](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent/session-limits.c#L268)
requires the caller to supply active usage and already incorporates the active
grant. Its effective endpoint is not a separate daily operand to add to a grant.

Shell's `dailyLimitTime` retains the effective endpoint inside the Shell process.
The public `org.gnome.Shell.ScreenTime` interface in
[50.1](https://github.com/GNOME/gnome-shell/blob/50.1/data/dbus-interfaces/org.gnome.Shell.ScreenTime.xml)
and [50.6](https://github.com/GNOME/gnome-shell/blob/50.6/data/dbus-interfaces/org.gnome.Shell.ScreenTime.xml)
exposes break-reminder state and last-break time, not that endpoint. No supported
external live-time command was found. Exporting the property again through the
child extension would preserve the dependency this task must remove.

The old return condition requiring a new upstream/native interface is superseded.
Upstream changes and native-accounting replacement are forbidden. The
[001a0 exploration](001a0-live-time-support.md) now evaluates existing public
observations with native history; 001a must pin a supportable composition rather
than wait for a new native API. Neither review supplies an installed result.
If existing inputs cannot establish the needed live state, retain that blocker;
do not compensate with guessed usage or broaden this reader-only brief silently.
The eventual delivered contract must include current uninterrupted use, define account/session identity,
daily versus effective-grant semantics, precision and clock domain, and expose
enough lifecycle/freshness information to reject stale or replaced observations.
001b must then pin that supported-version contract before implementation.
Reads must remain bounded and read-only. Preserve the original deadline through
helper/transport latency, using clock conversion bracketed by monotonic samples
when required; never restart a remaining duration on receipt. Clock discontinuity,
unavailable ownership, malformed replies or unprovable freshness must refuse the
read. A fresh daemon timestamp alone cannot make these saved-history estimates
usable. No product change, new test, build or installed result came from this
source review; no inspection resources remain owned.

## Validation and cleanup

Apply [AGENTS.md](../../AGENTS.md#product-boundaries) to implementation model,
effort and independent `backend_reviewer` review. Pause implementation during
that review, resolve actionable findings and review material backend revisions
again. Record the short review outcome in the normal handoff; review grants no
installed acceptance. Delegate only bounded, disjoint write ownership and close
helpers before final cleanup.

Apply the [test scope mandate](../Mandates/Test-Scope-Mandate.md). Reuse
[test_core.py](../../tests/unit/test_core.py) and the existing adapter/helper
coverage located through [test maintenance](../../tests/README.md); add only
distinct product/identity/failure assertions required by the reader change.
Preserve task 002's in-progress tests. No tests of task briefs, old histories or
ordinary test helpers. Run the lowest effective maintained affected checks and
the queued [package builder](../../tools/build_package.py) after the final
packaged edit, using [Makefile](../../Makefile) to assess build dependencies.

Use the [installed runner](../../tests/integration/README.md),
[VM mandate](../Mandates/VM-Mandate.MD),
[UI route mandate](../Mandates/UI-Automation-Mandate.MD) for any graphical
preparation and [shared session owner](../../tests/support/README.md) for live
integration. Read the [storage mandate](../Mandates/Test-Storage-Mandate.md)
before resource changes. Do not install on the development host; installation
uses only `make install` through maintained guest preparation.

On both declared targets, verify the actual broker/helper reads the selected
supported system interface under the correct child identity with the extension
endpoint unavailable. Establish valid clock/units and bounded refusal when that
source is unavailable, without writes caused by a read. Use the smallest
maintained installed diagnostic route for these integration assertions; do not
invent an executable selector in prose. These checks deliver the reader, not
task 002's uninterrupted-use, daily/grant, idle/lock/switch qualification or any
lock/app-access/customer-case acceptance. Task 002 must still implement and run
its complete `native-time` parameter on both systems.

Restore exact original limits, grants, extension state and any owned fault;
finish guest/session/resource cleanup through existing owners. Check changed
Markdown links. Record a short result and pass only with both installed results,
affected checks, required review, successful build and completed cleanup. Missing
prerequisites or a failed source on either platform leave this row unchecked.
