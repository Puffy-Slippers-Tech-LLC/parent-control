# 02 — Inventory callable paths and finish owned UI identity

**Recommended model: GPT-6 Astra. Effort: high.** This slice needs cross-layer
identity review and a complete accounting of reachable legacy paths.

**Prerequisite:** [01](01-legend-expansion.md) and [shared preflight](README.md).
**Status:** Not started. **Next:** [03](03-authentication-surfaces.md).

## Scope and work

Read [public guest adapter](../../../tests/e2e/accessible_ui.py),
[preview adapter](../../../tests/support/accessible_ui.py),
[automation contract](../../../tests/support/automation.py),
[preview launch](../../../tests/support/preview.py), and relevant product ID
definitions. Trace callers across `tests/e2e`, `tests/support`, `tests/ui`,
`tests/integration` and the launch/setup helpers. Include exported operations,
middleware, fallback/error/absence paths and retained entry points, even when
their scenarios are pending. Text search is a lead, not proof of compliance.

Maintain a compact current inventory in this brief: callable symbol, caller or
consumer, owning application/surface, selector/input mechanism, required ID,
disposition, and responsible task. Seed it with these families:

| Family | Initial condition to review | Owner |
| --- | --- | --- |
| Parent, About, denial, empty state, picker and popup absence | Recent ID edits need review and verification | 02 |
| Shared request form, kiosk, feedback and child controls | Preserve shared IDs and explicit account identity | 02 |
| Preview readiness, `wait_for_application`, Mutter keyboard/click entry | ID readiness, owned launch and coordinate refusal must survive | 02 |
| GDM, password recipient, Polkit/keyring middleware | Legacy selectors and recipient proofs need migration | 03 |
| Desktop/session/search, terminal, document viewer | Legacy selectors and provider mappings need migration | 04 |
| Perl image/pointer callers and `shell_overview.set_overview` | Prohibited routes remain callable | 05 |
| GUI fixture instances, native owner and runtime payload | Identity/lifecycle/mechanical review pending | 06 |

Resolve owned product/preview findings in this task; assign external and transport
findings to 03–05 without duplicating implementation. Audit any additional surface
against the existing provider catalogue, including file choosers/editors if found.
Record an explicit owner for every new finding before ending the session.

Verify recent changes to empty explanation reads, UID-scoped popup absence and
`parent-access-denied-window`. Preserve independent picker focus readback and
separate Enter commit, explicit child/approver identities, and ambiguous/wrong
surface refusal. Add missing product IDs through public accessibility before
implementing consumers; never place owned-product gaps in the provider backlog.

Check preview launch defaults return their owned process/log, name-based
application discovery is absent, `wait_for_application=True` refuses before
spawning, and `mutter_input.click_at` refuses before backend access. Preserve
normal keyboard delivery and disconnect-failure checks. Keep readiness owned by
the calling ID adapter and cleanup safe after discovery failure.

## Verification and completion

Use focused units first, including:

```sh
tools/run-unit-tests -q 'tests/unit/test_automation_ids.py' 'tests/unit/test_accessible_e2e_ui.py' 'tests/unit/test_mutter_input.py' 'tests/unit/test_ui_cleanup_safety.py' 'tests/unit/test_support.py'
```

Add changed owned-surface unit files to the literal selection. Where an owned ID
or interaction changes, run its relevant host UI file through `tools/run-ui-tests`
after the automatic safety gate. Source/string checks alone cannot establish
public exposure. Keep all final files in task 07/08's verification scope.

Complete when each reviewed entry has a disposition and owner, owned gaps are
fixed and checked, and no route is called compliant merely because it is unused
or has old passing tests. Record the number of unresolved paths by family;
subsequent tasks reduce this same scope rather than starting a replacement audit.
