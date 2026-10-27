# C07a — Prevent local full desktop access

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: D02.
Estimate: 30–60 min; session exception: one small confinement fix, review/build and both-target usability.

Apply the [desktop task contract](../Kiosk-Desktop-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Use D02's reviewed local desktop entries and actual GDM/PAM/account/session
callers. Its [frozen design](../SystemDesign/Kiosk-Confinement.md#d02-minimal-desktop-design-decision)
establishes no missing barrier yet. At this selected consumer, insert and complete
the planned public-selection qualification before product editing; saved routing
or privileged dedicated-session selection cannot establish child reachability.
Retain the existing mechanism if no escape is demonstrated, with the exact
target/action disposition and no unexercised alternate-command denial claim.
Add only a demonstrated missing narrow barrier to alternate graphical desktop
selection at the actual graphical-session admission boundary. Request-session
actions that yield a full desktop are extracted to C07s.
Retain passwordless request-only entry and ordinary-account desktop login.
Standalone terminal/TTY and other shortcut results remain with C07t in the
remaining plan; do not duplicate them here.

Keep this slice limited to one demonstrated defect at the reviewed local desktop
boundary and its direct consumers. Bind the predicate to the actual selected
session/launch, not a saved preference or a familiar PAM service-name list. A
shell denial alone is not desktop proof. Use D02's finite benign/fault controls.
Prepare missing automation before editing; split independent fixes rather than
grow this task or defer its installed gate.

Cover each defense's normal-use and deliberate-child outcomes through existing
host tests and installed-case bindings. Follow [simple tests](../Kiosk-Desktop-Plan.md#simple-tests):
add a case only for a distinct gap; reuse shared setup and safety checks.
If the baseline already satisfies a route, reuse its applicable checks and
document that instead of adding restrictions or duplicate tests.
Keep expected results and finite route parameters in their existing owners.
Run affected tests, independent product/backend review and final build.

Before completing, pass the master's
[bounded confinement usability check](../Kiosk-Desktop-Plan.md#bounded-confinement-usability-check)
and directly affected benign/fault controls on both targets with this candidate.
Keep ordinary-account login usable and finish owned restoration. A failed or
unrun target keeps this task open before automatic commit/push; later C11d/C12d
route acceptance cannot supply its missing usability result.
