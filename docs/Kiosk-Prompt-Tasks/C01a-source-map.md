# C01a — Map release and active session source

Acceptance: review

Required tasks: Baseline.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Compare the pinned release, checked-in HEAD and the old execution plan's relevant
staged, unstaged and untracked work together. This slice maps session, native
runtime, account and PAM entry. C01b maps frontend/broker features; C01c maps
build/test consumers. Start with the release session desktop/target/app/agent
units, kiosk login check, native PAM branches and provisioning. Follow complete
native callers/callees and give C01b/C01c exact cross-component symbols.

Record a file/function table in the existing confinement design owner: release
source, current equivalent, active delta, confinement responsibility, preserved
main feature and test owner. Include committed private-view/material/preparation
code, active startup/PAM/agent modules and data/kiosk-runtime. Mark active deltas
as old-plan work; obsolete code may be deleted during cleanup without preserving
past effort. Separate required behavior from committed or unfinished mechanisms.
Verify the release pin exists; do not replace it with the branch tip.

This task supplies source lineage, not a protection design or product acceptance.
C01 decides replacement boundaries after C01b/C01c. Check entries against source,
run links/plan checks, and retain unresolved shared-function questions there.
