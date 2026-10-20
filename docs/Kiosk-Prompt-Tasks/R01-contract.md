# R01 — Settle the admission and confinement contract

Acceptance: review

Requires Baseline. Read the [master](../Kiosk-Resilience-Plan.md), the
[confinement owner](../SystemDesign/Kiosk-Confinement.md), relevant
[lifecycle](../SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle) and
[broker authorization](../SystemDesign/Broker.md#broker-interface-and-roles).
Follow the master’s shared execution and review contracts.

## Deliverable

Trace the whole actual path: GDM selection/authentication, account routing,
manager startup, PAM open/close/setcred, final exec, compositor, request form,
service activation, parent authentication, exit and next entry. Read the complete
affected functions in `pam_oh_no_parent_control.c`, `oh-no-parent-control-login-check`,
`kiosk_*startup.h`, preparation/policy modules, `kiosk_session.c` and packaging PAM
integration. Follow their consumed data and callers; a grep inventory is not an audit.

Write one explicit decision/rejection ledger in the design owner. For every
existing admission-failure family, name its authority and current source, the
child-reachable risk (or actual essential setup/admin-policy fault), and the
decision: remove, tolerate, exclude an input, degrade a feature, recover, or retain
a narrowly justified rejection. Include optional resource identity, ambient
layout/limits, manager equality, locks/timeouts, inherited credentials, PAM
bytes/modules, effective access policy, executable/configuration loading and
mandatory enforcement. State positive and negative controls, an actionable
customer explanation and a precise sanitized diagnostic reason. An optional
proof/diagnostic failure cannot substitute for an actual missing boundary.

Choose one minimal startup/lifecycle design. Make consumed configuration/module/
plugin/unit/activation searches explicit; do not require a universal program
allowlist or host filesystem reconstruction. Define how known escape routes are
blocked independent of program names, how account/management boundaries survive,
and how healthy reuse/owned renewal works without adopting foreign state.
Do not classify unknown host configuration as an attack. Map old assertions to
the new behavioral requirements before authorizing later test changes.

## Validation and close-out

Require the master's independent Astra XHigh architecture review and address its
actionable findings. Review both backends, real GDM credentials, actual first
execution, pre-boundary children, teardown and privileged parent approval.
Specify the finite R02–R04 proof, measurable waiting/recovery budgets and exact
failure/restore outcomes. Resolve architecture questions here; do not defer the
central trust/lifetime decision to a test run.

Check links and maintained documentation consistency. Record the chosen design
and remaining implementation limits in existing owners; no new evidence archive.
No product implementation or installed acceptance belongs to this task.
