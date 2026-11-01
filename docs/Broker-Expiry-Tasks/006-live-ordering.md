# 006 — Keep expiry moving during approval

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: 004, 005.
Estimate: 30–60 minutes; one open-challenge history on both targets.

Read the [master](../Broker-Expiry-Plan.md) and current management/authentication
transaction owners. Extend system-282 with planned parameter `expiry-ordering`
(unimplemented), using existing authentication and public management mechanics.

Hold a genuine approval challenge open across the child's original deadline;
expiry must still protect input, without limiting the parent's human decision
time. Resolve/cancel it using established routes and verify retained work.
Keep another foreground user's input/work unaffected during target expiry or
recovery; observe the target transition separately. Before-access exposure
still belongs to task 171 and receives no credit from a final lock here.

Prepare authentication discovery and the expiry observer under ample setup
time. Establish the genuine challenge comfortably before the measured expiry
and confirm it remains pending across that original deadline. Use readiness
gates where current public transaction rules permit them; do not assume another
grant can commit during authentication or race password entry against a final
countdown. Challenge resolution and work recovery retain their separate budgets.

Each attempt owns finite state/order, declared windows and cleanup. Run changed
host checks and new installed histories on both targets. Production inability
to progress is a blocker under failure handling, not authority to rewrite it.

Policy races and session replacement have their own bounded rows 006a/006b.
