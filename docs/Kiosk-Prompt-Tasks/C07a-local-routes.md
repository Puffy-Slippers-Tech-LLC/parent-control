# C07a — Prevent local full desktop access

Acceptance: host

Required tasks: D02.
Estimate: 20–30 min.

Apply the [desktop task contract](../Kiosk-Desktop-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Use D02's reviewed local desktop entries and actual GDM/PAM/account/session
callers. Add only the missing narrow barrier to alternate graphical desktop
selection at the actual graphical-session admission boundary. Request-session
actions that yield a full desktop are extracted to C07s.
Retain passwordless request-only entry and ordinary-account desktop login.
Standalone terminal/TTY and other shortcut results remain with C07t in the
remaining plan; do not duplicate them here.

Keep this slice limited to the reviewed local desktop boundary and its direct
consumers. A shell denial or saved session preference alone is not desktop proof.
Independent missing work becomes a bounded prerequisite at this consumer.

Pair each defense with its normal-use and deliberate-child controls in targeted
host tests and existing installed-case bindings. If the baseline already
satisfies a route, verify and document that instead of adding restrictions.
Keep expected results and finite route parameters in their existing owners.
Run affected tests, independent product/backend review and final build.
