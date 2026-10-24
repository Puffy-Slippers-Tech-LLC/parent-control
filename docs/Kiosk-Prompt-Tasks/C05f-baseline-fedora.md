# C05f — Prove baseline usability on Fedora

Acceptance: installed
Targets: onpc-Fedora44

Required tasks: C05u.
Estimate: 15–30 min for evidence acceptance; 30–60 min if renewal is needed;
session exception: complete baseline customer journey.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Accept the rebuilt Fedora candidate against every assertion in the
[finite baseline recipe](../TestAutomation/E2E-Scenario-Recipes.md#c04b-baseline-public-use-slice),
including its separate existing feature and human-pause checks, through actual
Fedora GDM/PAM/SELinux and genuine parent authentication. Preserve ordinary-user
authentication and privilege transitions. General feature expansion follows
the [reuse map](../TestAutomation/E2E-Building-Blocks.md#cross-plan-baseline-reuse).

First apply the
[complete baseline evidence-reuse contract](../TestAutomation/E2E-Execution-Contracts.md#complete-baseline-evidence-reuse)
to C04j's retained Fedora history and
[C04's handoff](../TestAutomation/E2E-Building-Blocks.md#c04-readiness-audit). Record the independent
applicability check and original public results as installed acceptance when
valid. Run a complete core history that never passed or was invalidated by a
concrete change through
`tools/run-tests --vm 'onpc-Fedora44' integration 'check_e2e_baseline_journey'`
with the recipe's original inputs and bounds.
Renew missing or invalidated separate feature/pause slices separately. Separate operation
qualifications or an Ubuntu result cannot supply Fedora's ordered history.
Trust completed prerequisite results; expired diagnostics do not require
report recovery or repeating passed work under the
[completion policy](../Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery).

Shared repairs need independent review/build and reruns of invalidated complete
Ubuntu histories before this gate closes. Preserve valid unchanged results;
report both-target candidate applicability, desktop gaps for D01/D02 and other
ordinary route gaps for C06a/C06.
This is baseline usability, not final defense or Fedora release qualification.
Retain exact receipts and finish restoration for any new execution. Report
installed acceptance against `onpc-Fedora44`, with both-target applicability
findings and original complete-history/cleanup references. Close only C05f when
selected; this reuse grants no final post-protection acceptance.

This is the baseline queue's final row. Close with matching baseline product,
automation and current documentation, exact both-target evidence applicability
and completed owned cleanup. Hand desktop gaps to
[desktop D01](D01-desktop-review.md) and other deliberate-route gaps to
[remaining-plan C06a](C06a-login-review.md). Both verify applicable accepted
receipts before review; C06a additionally requires accepted desktop D04.
New protections and their separately owned final acceptance do not extend
this baseline or become a release prerequisite through that handoff.
