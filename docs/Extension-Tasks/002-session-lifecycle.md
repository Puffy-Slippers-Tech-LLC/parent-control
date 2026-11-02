# 002 — Keep recovery safe across session and broker changes

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Category: system. Requires: 001. Estimate: 30–60 minutes.
Session exception: retain each real session/bus replacement through restoration;
resetting the guest mid-history would conceal stale ownership or pending work.

Read the [master](../Extension-Plan.md), [monitor contract](../SystemDesign/Screen-Time.md#extension-enablement-monitoring),
`ExtensionMonitor` and the existing monitor unit/private-bus checks. Reuse task
001's installed operations, not its complete acceptance history.

Add only the missing installed lifecycle boundaries:

- Normal logout and a fresh child session reattach to the current bus/Shell without
  an error report. Include ordinary logout soon after successful recovery.
- Replace/lose the owned user-bus connection and then recover; stale callbacks
  must not act on another account or an obsolete session. Exercise real owner
  delivery and runtime identity rather than only a synthetic signal.
- Hold a genuine broker transaction across the early retry interval, request
  disablement, then release it. Recovery remains pending at low cost and resumes;
  do not impose a timeout on human authentication or replay an approval.
- Stop/restart the broker with a pending observation/recovery. Observe owned
  resources settle and no late activation/report after controls are off or the
  old worker has stopped. Reuse host cancellation matrices; do not duplicate them.

Keep actual account policy and original grants unchanged except for any genuine
operation explicitly needed by the case. Use existing guarded session/transport
mechanics. New installed selector/binding remains unimplemented; register only a
distinct uncovered history. Verify both targets and finish the master's cleanup.
