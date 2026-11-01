# 001a0 — Explore timing without the extension

Acceptance: review

Required tasks: 001.
Estimate: 20–30 minutes; one bounded row 4 feasibility/design review.

## Purpose and scope

Evaluate the candidate in [Replace Main.timeLimitsManager](../SystemDesign/Replace-Main.timeLimitsManager.md):
existing logind activity observations combined with Malcontent's recorded usage
and a transient unfinished interval. Keep GNOME recording and Malcontent storage;
upstream changes, native patches and a replacement accountant are forbidden.
The old system-support proposal is superseded, not an implementation prerequisite.

Account for Ubuntu 26.04 and Fedora 44. Distinguish public interface availability
from a working composition. This task authorizes source/design exploration only,
not an observer prototype, persistent ledger, reader implementation, installed
acceptance or row 3 scheduler. Row 3's exploration has no dependency on this task.

## Reading and result

Read the [master](../Broker-Expiry-Plan.md#native-time-prerequisite-plan), the
row 4 exploration, [001a's contract boundary](001a-live-time-source.md#reading-and-decision)
and [recorded direct-reader findings](001b-live-time-reader.md#source-review-and-return-condition).
Follow the exploration's scoped links to owning contracts and official source.
Reuse the rejected saved-history finding rather than searching again for a
direct export that is known to be absent in the reviewed versions.

Follow [source discovery](../Approval-Tools.md#source-discovery-before-reads).
Use approved public research and checkout reads. If guest inspection proves
necessary, first read the [VM mandate](../Mandates/VM-Mandate.MD) and use maintained
non-graphical routes with owned cleanup. No installed acceptance is required or
earned by this review task. Do not launch another workflow.

Update the row 4 exploration with one recommendation: feasible, feasible only
within a stated scope, or blocked. Resolve or explicitly identify initial
mid-interval synchronization, overlap reconciliation, native precision,
idle/lock/switch/sleep, session identity, owner loss and broker-restart gaps.
Do not invent usage to fill an unknowable interval or propose upstream work.
Obtain a bounded read-only independent design review and resolve its findings;
this is not the later backend code review or installed qualification.

Identify the smallest future adapter/observer integration and affected consumers.
If it exceeds 001b's old helper-only scope, record the required bounded brief
revision and leave delivery deferred. Do not implement or schedule a general
accounting engine to finish the review. A negative feasibility finding may finish
this bounded exploration with an explicit blocker; it cannot pass 001a or 002.

## Validation and cleanup

Review the recommendation against the row 4 questions and current specification
and design owners. A usable result identifies every unresolved delivery gate;
an unexamined choice is not a concrete recommendation. No source or consumer is
declared ready merely because the exploration is complete.
Apply the [test scope mandate](../Mandates/Test-Scope-Mandate.md); add no tests
of plan documents or old histories. Check changed Markdown links and queue/brief
dependencies, preserve all existing task scopes and completed rows, and finish
owned inspection/helper cleanup. Record a short design result in this row only.
