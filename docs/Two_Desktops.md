# Two desktops for one child: open question

Can a child use two separate, simultaneously retained ordinary GNOME desktops
for the same account through a supported public sign-in route, and can the
family return to each original desktop after a parent changes that child's
access?

By user decision, this question and its six scenarios are removed from execution
scheduling in Plans A, B and C. They have not passed. This document preserves
the question, former scenario identities and expected product behavior; it is
not an execution plan. Ordinary single-desktop and cross-user coverage remains
unchanged.

## What counts as two desktops

Both desktops belong to the same child account and remain alive at the same
time. Each has its own recognizable original activity and can be revisited
without replacing the other desktop. Only one needs to be in the foreground
at a time.

Two windows or two workspaces in one desktop do not establish this situation.
Jordan's desktop and Riley's desktop belong to different accounts and establish
cross-user isolation instead. Signing in twice and returning to the same
retained session also does not establish two desktops. Signing out and creating
a replacement desktop loses the simultaneous-retention property.

The original route question had task identity **143**. Ordinary GDM selection
may resume the account's existing desktop. No supported ordinary GNOME public
route to two distinct retained desktops for one child has been established by
this review, and no installed two-desktop qualification is claimed. That is an
unresolved route question, not a conclusion that all GNOME configurations make
it impossible.

## Family situation and expected behavior

Jordan is the child whose access the parent changes. Jordan has two retained
desktops, each containing identifiable original work. Riley has a separate
retained desktop with identifiable work as the unrelated-child comparison.
The parent uses the normal Parent App or genuinely approves Jordan's request.
After the action, returning to an original desktop means observing its original
work, not opening a replacement window with similar contents.

Use these app roles to describe the finite scenarios: **A** is Always Allowed,
**H** is Hard Blocked and **S** is Soft Blocked. A genuine approval including
soft apps permits S to open before a later exclusion or revocation. An app that
will become blocked by a save can initially be Allowed so its original activity
exists before that save. An already-open app that was already Hard Blocked
would require its own supported public history; its existence is not assumed.

**D** means the child's remaining daily time and **G** the remaining one-time
grant. The original non-expiry examples used zero daily allowance with a real
20-minute grant, or a saved 30-minute daily allowance with a real 20-minute
addition when a grant was needed. A saved allowance is not a fresh remaining
balance. Positive-time examples require actual time still remaining when each
desktop is revisited. Approval adds its requested duration to the larger of D
and G; it does not add D and G together or give each desktop a separate grant.

The [account-isolation specification](Specification.md#accounts-and-access)
applies the change to Jordan's account, including Jordan's retained desktops,
while preserving Riley's settings and grants. The
[application-access specification](Specification.md#application-access) and
[revocation specification](Specification.md#revocation-persistence-and-failures)
define closure and launch effects. Those account-wide requirements remain
meaningful even while the public two-desktop situation is unresolved.

## Preserved scenarios

The following six rows retain the former case IDs as references. Each describes
one family history with the same two Jordan desktops and Riley's original work
retained throughout the parent action.

| Former case / task | Parent action and starting situation | Expected result across the original desktops |
| --- | --- | --- |
| **18 — zero-multiple / 144** | Jordan has D=0, a real positive soft-included grant, and original A/S activities. The parent opens Revoke, cancels, compares the balances and activities, then confirms Revoke. | Cancel preserves time and original activities, allowing for normal elapsed time. Confirm removes the grant and restores the saved app restrictions. With D=G=0, correct-password return to Jordan's retained desktop is denied for time restriction. A locked desktop does not reveal whether its hidden apps closed. Riley's original activity remains usable. |
| **20 — remaining-multiple / 145** | Jordan has positive daily time, a real soft-included grant and original A/S activities. The parent cancels Revoke and compares balances and activities, then confirms it. | Cancel preserves the original access and work. Confirm clears G and preserves unused D and saved rules. On each Jordan desktop, the original S activity is closed, original A work remains usable, and new H/S launches are denied while daily access remains available. Riley's original activity remains usable. |
| **112 — save / 146** | Jordan has positive daily time and work on both desktops. The parent makes one app-policy save that introduces a block for an open app, such as changing that app from Allowed to Hard Blocked. | Each Jordan desktop shows the original newly blocked activity closed and the new blocked launch denied. Unaffected Allowed work remains usable. Closure follows the actual save delta; saving an unchanged block does not close every previously blocked app. Riley's original work and access remain unchanged. |
| **113 — approve-without-soft / 147** | Jordan has positive daily time and original A/S activities made possible by a previous real soft-included approval. The parent approves one real request excluding soft apps. | The complete saved H/S launch restrictions apply, matching blocked activities close on each Jordan desktop before the new grant is written, and Allowed work remains usable. New H/S launches are denied. The account receives the one calculated grant; Riley's original work and access remain unchanged. |
| **114 — approve-with-soft / 148** | Jordan has positive daily time and original activities on both desktops. The parent approves one real request including soft apps. | Original activities are preserved, S can be launched and used from each Jordan desktop, and new H launches remain denied. Approval itself terminates no open apps, including an already-open hard-blocked app if a supported public history established one. Riley's original work and access remain unchanged. |
| **115 — revoke / 149** | Jordan has positive daily time, a real soft-included grant and original A/S activities on both desktops. The parent confirms one Revoke. | G is cleared and unused D remains. Original matching blocked activities close across Jordan's desktops; original Allowed work remains usable. New H/S launches are denied while daily access remains available. Riley's original work and access remain unchanged. |

The zero-time row preserves its original retained-entry denial scope; it does
not claim a separate foreground immediate-lock result. In every row, Riley's
comparison concerns the same original activity and its continued use, not just
the presence of another account at sign-in. Parent changes must not end Riley's
session or change Riley's saved policy, allowance or grant.

## What the implementation establishes and leaves open

The broker's [transaction boundary](SystemDesign/Broker.md#authorization-and-grant-transactions)
targets a child account rather than one selected desktop. The
[running-application boundary](SystemDesign/Applications.md#running-application-identity)
describes verified child-owned processes across retained sessions. App-policy
save, approval and revocation have different closure rules; natural expiry does
not itself close apps. The [screen-time design](SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement)
owns lock and retained-entry behavior.

Source review of the broker's policy save, approval, revocation and
[application termination](../broker/oh_no_parent_control/app_termination.py)
supports those account-wide boundaries. It does not demonstrate that a family
can create and revisit the two required same-account desktops. Existing
[retained-activity operations](TestAutomation/E2E-Building-Blocks.md#reusable-journey-fragments)
cover distinct users and reject duplicate users in their finite input list;
they do not establish this same-child route.

A future investigation could establish whether an ordinary supported desktop
configuration already exposes that route, how a family distinguishes and
revisits both original desktops, and whether this is a customer-facing situation
or an engineering-only account-isolation concern. Creating new seats, nested
compositors, display servers or remote-desktop infrastructure would change that
question rather than answer how the existing ordinary desktop behaves. This
document selects no such infrastructure and schedules no implementation.
