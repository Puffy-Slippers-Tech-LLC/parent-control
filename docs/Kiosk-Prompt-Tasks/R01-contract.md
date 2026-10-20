# R01 — Review the integrated admission contract

Acceptance: review

Required tasks: R01a — execution/activation; R01b — authentication policy;
R01c — approval lifetime; R01d — configuration ownership;
R01e — readiness/recovery/activation.
Estimate: 30–45 minutes.

Read the [master](../Kiosk-Resilience-Plan.md), the
[confinement owner](../SystemDesign/Kiosk-Confinement.md), relevant
[lifecycle](../SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle) and
[broker authorization](../SystemDesign/Broker.md#broker-interface-and-roles).
R01e's [selected readiness and activation decision](../SystemDesign/Lifecycle.md#r01e-readiness-and-activation-decision)
owns prerequisite classes, state/renewal rules, the measured deadline and input
activation mapping; review their composition here rather than resettling them
without a concrete finding.
Follow the master’s shared execution and review contracts.

## Session boundary

R01a–R01e extract the source audits and individual mechanism decisions. This
task integrates their delivered decisions, resolves cross-boundary conflicts,
maps old assertions and obtains the mandatory independent architecture review.
Do not repeat unchanged audits or implement the product. The following is the
cumulative audit/decision coverage required of R01 and its prerequisites.

## Cumulative deliverable

Trace the whole actual path: package configuration, account provisioning,
AccountsService visibility repair, quarantine release, GDM selection/authentication,
account routing, manager startup, PAM open/close/setcred, final exec, compositor,
request form, service activation, parent authentication, exit and next entry.
Read complete affected functions in `pam_oh_no_parent_control.c`,
`oh-no-parent-control-login-check`,
`kiosk_*startup.h`, preparation/policy modules, `kiosk_session.c` and packaging PAM
integration. Include `packaging/lifecycle/postinst.in` and `tools/provision.py`'s
`accounts_service_provision_kiosk()`, `accounts_service_set_icon_file()`,
`repair_kiosk_visibility()` and cache-version/transaction callers. Follow their
consumed data and callers; a grep inventory is not an audit.
Include broker construction through D-Bus registration, extension refresh for
other children and the native-agent locale preparation path. Follow
`Service._start_policy()`, `Broker.refresh_enabled_extensions()`,
`ExtensionManager.set_enabled()` and `KioskAgentLocale.prepare()` through their
callers, failures and public outcomes.

Write one explicit decision/rejection ledger in the design owner. For every
existing admission-failure family, name its authority and current source, the
child-reachable risk (or actual essential setup/admin-policy fault), and the
decision: remove, tolerate, exclude an input, degrade a feature, recover, or retain
a narrowly justified rejection. Include optional resource identity, ambient
layout/limits, manager equality, locks/timeouts, inherited credentials, PAM
bytes/modules, effective access policy, executable/configuration loading,
pre-GDM setup failures and mandatory enforcement. Distinguish product-owned
temporary expiry from administrator denial. Assign optional icon degradation
to R08a, capability/schema-based visibility repair to R05a and safe quarantine
release to R05b under the [lifecycle target](../SystemDesign/Lifecycle.md#prospective-configuration-and-activation-recovery).
That target also owns cross-account readiness and the ambiguous same-value
administrator-expiry case. Assign bounded broker isolation/recovery to R06b and
native authentication-language fallback to R08b. Trace an unavailable broker to
its actual prerequisite rather than treating every such result as globally
missing enforcement.
State positive and negative controls, an actionable customer explanation and a
precise sanitized diagnostic reason. An optional
proof/diagnostic failure cannot substitute for an actual missing boundary.

Choose one minimal startup/lifecycle design. Make consumed configuration/module/
plugin/unit/activation searches explicit; do not require a universal program
allowlist or host filesystem reconstruction. Define how known escape routes are
blocked independent of program names, how account/management boundaries survive,
and how healthy reuse/owned renewal works without adopting foreign state.
Resolve each [architecture decision](../SystemDesign/Kiosk-Confinement.md#architecture-decisions-required-before-the-entry-proof)
with a concrete mechanism and source/API basis, including automatic activation,
effective PAM/empty-token policy, approval/session identity, update activation
classes and observable readiness. Do not classify unknown host configuration as
an attack. Map old assertions, including reliability 006a/006b and cases 290/291,
to the new behavioral requirements before authorizing later test changes.
Include the existing C-only native-locale refusal test and the
[standalone proof catalogue](../Kiosk-Confinement-Proof.md#evidence-scope).
Resolve the [approval/commit ordering](../SystemDesign/Broker.md#prospective-kiosk-approval-lifetime)
with the Specification/Broker owners before R02a: distinguish pending authentication
from post-authentication work, state the externally visible cancellation boundary
and require both event orderings through a delayed usage query and reentry.
Use actual child write authority on consumed inputs; neither unrelated mutable
contents nor trusted-administrator-only group write is automatically a risk.

## Validation and close-out

Require the master's independent Astra XHigh architecture review and address its
actionable findings. Review both backends, real GDM credentials, actual first
execution, pre-boundary children, teardown and privileged parent approval.
Specify the finite R02a–R04 proof, including the master's unfamiliar benign PAM
and automatically activated service fixtures. Declare measurable end-to-end
entry/recovery budgets from available observations, with R03/R04 checking them
against the actual route, and exact failure/restore outcomes. Resolve architecture
questions here; do not defer the central trust/lifetime decision to a test run.
Re-estimate affected queue rows and briefs from the chosen mechanism, review/build
scope and measured history durations. Keep independent discoveries bounded under
the shared execution contract; provisional estimates cannot cut acceptance.

Check links and maintained documentation consistency. Record the chosen design
and remaining implementation limits in existing owners; no new evidence archive.
No product implementation or installed acceptance belongs to this task.
Session exception: keep integrated cross-platform architecture review, actionable
revision and final proof-plan agreement together; the independent source/decision
work has been extracted into R01a–R01e. Close only R01 and advance to R02a.
