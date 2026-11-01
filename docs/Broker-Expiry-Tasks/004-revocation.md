# 004 — Check revocation on the active desktop

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: 001.
Estimate: 45–75 minutes; indivisible revoke/control histories on both targets.

Read the [master](../Broker-Expiry-Plan.md), original revocation rationale and
canonical cases 17–20. Extend system-282; planned parameter `foreground-revoke`
(unimplemented). Use an authorized public management connection while the child
remains in the foreground, without switching to Parent or forging client claims.

First on the production path, revoke the live grant with zero daily balance.
Observe immediate bounded input-protecting lock and retained work, using the
original deadline and task 001's predeclared revocation bound. Use a positive
daily-balance control: grant removal must leave existing daily access usable.
Verify live AccountsService state defeats a stale cached client grant.

Prepare the management connection, foreground work and lock observer before
revocation; anchor its response bound to the original observed revoke, not the
later return/navigation. Give the positive-daily control ample remaining access
for its complete input/work check so incidental daily exhaustion cannot mimic
a revocation failure.
Then isolate the old expiry request to qualify the native boundary; distinguish
this diagnostic result from the production-path regression and future broker
replacement qualification. An unmet native obligation stays a handover blocker;
the disabled-path diagnostic is not an installed enforcement pass. Completion
requires passing production-path assertions on both targets and truthful native
characterization, not a native pass manufactured by reactivating the extension.

Retained return, Cancel, alternate desktop and full peer journey matrices belong
to tasks 084/085/143–145; do not reimplement them here. Their pending acceptance
remains required even when this foreground delta passes.

Run only the new/affected engineering checks on both targets. Restore grants,
limits, extension state and owned sessions without editing usage to repair a
result; follow master cleanup and completion.
