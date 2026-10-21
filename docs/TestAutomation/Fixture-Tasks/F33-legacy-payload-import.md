# F33 — Import and retire the full legacy movable inventory

Acceptance: host
Requires: F50

## Scope and implementation

Implement the [legacy ownership transfer](../Fixture-Design.md#profile-contraction-and-activation-transaction)
using F24/F30's recognized original proof. Read complete baseline declarations,
fixture/native receipts, baseline_guest.prepare and guest-file identity helpers.
Import every original movable output into a transaction, including unrequested
payloads, launcher copies, exact native entries and retained preparation checkout
sources. Leave environmental masks/settings and scenario-owned state with their
existing owners. No old movable member may escape both the active receipt and
retirement journal when a smaller first subset is requested.

Verify staged source copies as data against the accepted original preparation
closure; never run them. Delete only exact owned matching files and subsequently
empty owned directories. Preserve unknown children and refuse changed bytes,
metadata, links or mounts. Supply the minimum environment staging declaration
to F11/F12, which apply it together with their dependency-digest split. Do not
change the legacy preparation writer or remove inputs it still hashes while
preparing a legacy baseline. Attempt-owned retirement occurs only after original
proof is preserved and preparation is complete; cleanup restores its original
snapshot rather than trying to rerun the stripped preparation checkout.
Do not claim arbitrary root-owned files by digest alone. F15 later composes the
import/removal actions with its barrier and placement state machine.

## Finite validation and cleanup

Use private complete original receipts/trees to request one small subset from a
full legacy fixture set. Prove every other movable input is scheduled for exact
retirement, shared requirements stay, environmental files remain and old source
copies cannot survive by renaming. Inject missing proof, unexpected tree children,
substituted files and interrupted import/removal; preserve unrelated state.
Run scoped baseline/fixture/guest-file safety checks and resource review.
No VM or protected host files are touched. Update support/clean-capture owners
and close through the [master](../Fixture-Execution-Plan.md).
