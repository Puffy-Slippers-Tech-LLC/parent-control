# 009a1 — Implement canonical authentication history

Acceptance: host

Requires 004 and 008. Staged prerequisite of
[009a](009a-auth-ubuntu.md), inserted at its active boundary under the
[master's split route](../Kiosk-Prompt.md#smaller-execution-slices).

Implement/register only 008a/008's settled supported and effective incompatible
branches, reusing current native PAM environment/first-configuration and public
GDM observers. Select one effective incompatible branch per backend as specified
by that contract, not an arbitrary PAM matrix. Verify fixture effectiveness,
closed refusal/diagnostic, unchanged administrator policy and ordinary accounts,
exact restoration and fresh usable passwordless public entry in the canonical
history. Never enable null tokens or enter a kiosk password to make it pass.

Add focused host fixture/effective-policy/registration/ownership controls and
resource review. Run their lowest effective maintained selection, documentation
and coverage checks, and build after packaged changes. Unsettled product behavior
follows the owning decision contract; substantial independent new mechanics need
a finite prerequisite. No VM acceptance belongs here. Finish owned cleanup and
record exact selectors/input closure for 009a/009, which retain the whole
installed policy/refusal/restoration/ordinary-account/public-reentry histories.
