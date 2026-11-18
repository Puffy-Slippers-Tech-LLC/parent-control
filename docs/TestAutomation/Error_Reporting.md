# Detect product errors in VM tests

Task queue: [Ordered task queue](Error_Reporting/Task_Queue.md).
Next task: **001 — [Make product failures visible to the runner](Error_Reporting/001.md)**.

Every VM test case should fail if the current product produces an unexpected
error during its owned execution, including errors that never open a report
dialog. The runner makes that decision in code. An unexpected fault goes through
the normal exact-case repair path under `fix-tests` after owned cleanup. Clean
cases and cases with only expected faults and passing assertions use zero model
calls. An unavailable required observation prevents a pass and is reported as
an infrastructure blocker when it is the sole issue.

Use one structured product failure signal and one shared evaluator. The
evaluator matches on component, a stable fault category and the case's explicit
fault window. The allowance accepts any number of matching events, including
zero. The case's assertions establish the intended fault and recovery. The same
category outside the window and unrelated categories inside it remain errors.
Exception details and source locations are diagnostic context.

Scope covers the latest product build across system pytest, VM-backed standalone
checks selected through the aggregate or explicitly by name, and E2E, including
case-owned clean installation. In an upgrade history, begin at the existing
boundary that verifies current-build execution. The historical and mixed-code
transition spans are outside the observed interval. Existing customer assertions
remain in force throughout.

Follow the [execution plan workflow](../Execution-Plans.md#plan-format),
[test documentation map](README.md), and [VM mandate](../Mandates/VM-Mandate.MD).
Update the owning contracts as each behavior lands. The plan records work and
acceptance for this change.
