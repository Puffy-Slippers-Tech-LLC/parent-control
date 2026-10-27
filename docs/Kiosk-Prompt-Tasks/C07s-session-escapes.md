# C07s — Prevent desktop launches from the request session

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: C07a, C07s1.
Estimate: 30–60 min; session exception: one small confinement fix, review/build and both-target usability.

Apply the [desktop task contract](../Kiosk-Desktop-Plan.md#task-execution-contract).

## Session boundary and deliverable

Extract request-session desktop escapes from C07a. Use D01/D02's finite
action/launch map to close one demonstrated route to a full kiosk desktop.
C07s1 supplies the qualified shared shortcut/results and working ordinary
desktop controls on both targets, including Fedora's permanently prepared
terminal shortcut. Reuse its [exact scope and limits](../TestAutomation/E2E-Building-Blocks.md#request-session-shortcut-results);
its checks give no C07s acceptance credit.
Follow the [frozen design and qualification allocation](../SystemDesign/Kiosk-Confinement.md#d02-minimal-desktop-design-decision):
insert and complete any independently missing qualification before product
editing. Existing action barriers remain effective in source; add no restriction
without a demonstrated escape. C07s1 observed only a usable request after each
of the four shortcuts, with working ordinary-desktop witnesses on both targets;
that finite result is not a universal desktop fence.
C07a owns graphical-session admission; standalone terminal/TTY,
SSH and other exposed-action results retain their remaining-plan owners.

Cover each justified barrier with permitted form/genuine approval controls and
ordinary-account/shared-overlay behavior. Reuse applicable checks for effective
routes. Follow [simple tests](../Kiosk-Desktop-Plan.md#simple-tests): update
directly affected host regressions and local installed bindings consumed by D03
and C11d/C12d; add cases only for uncovered outcomes and keep stable case IDs.

Run scoped checks, required independent backend review where triggered and the
final packaged-input build. New independent provider automation needs a bounded
installed prerequisite before product editing; a host pass grants no qualification.
Split independent defects before editing rather than combine launch routes here.
Record the finite changes, candidate/evidence impact and owned restoration in the
existing design/test owners.

Before completing, pass the master's
[bounded confinement usability check](../Kiosk-Desktop-Plan.md#bounded-confinement-usability-check)
and directly affected benign/fault controls on both targets with this candidate.
Block the prohibited action without making unrelated request actions admission
conditions. Include a shared-overlay request only if that caller changes. Finish
owned restoration; either target failing or not run keeps this task open before
automatic commit/push. C11d/C12d retain final route-negative acceptance.
