# 009a — Qualify Ubuntu authentication policy

Acceptance: installed
Targets: onpc-Ubuntu26.04

## First action when selected

Apply the developer-requested [staged split](../Kiosk-Prompt.md#smaller-execution-slices).
Insert this unchecked prerequisite immediately before the active consumer:

| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | 009a1 | [Implement canonical authentication history](009a1-auth-history-host.md) | 004, 008 | Register and host-validate the settled effective-policy/refusal/restoration public-entry history | 20–30 min |

Use the queue-relative `Kiosk-Prompt-Tasks/...` link. Add 009a1 to this consumer's
Requires, preserving 004, 008, its Scope and the complete installed history below.
Move Next task to 009a1, finish owned cleanup and return `prerequisite_required`.
Then execute this original consumer's whole Ubuntu acceptance. The prerequisite
supplies implementation only; it grants no installed credit.

Use the [master](../Kiosk-Prompt.md), 008's settled contract, existing native PAM
environment/first-configuration mechanics and public GDM observers. Implement/
register the canonical finite selector in its current owner.

Prove supported empty-token authentication and usable station entry. Verify
the chosen incompatible fixture changes the effective native auth path, then
require intended configuration/admission refusal and sanitized reason. Preserve
ordinary-account authentication and administrator policy. Observe greeter behavior
only if this fixture legitimately reaches GDM; never enter a kiosk password.

Restore exact owned authentication state and require fresh successful public
entry. Session exception: initial implementation plus the complete effective
policy/refusal/restoration/recovery/cleanup history may take 30–60 minutes.
Extract independent new mechanics first. Run affected host/build checks, retain
first failures, exact package/PAM identities and cleanup; provide Ubuntu receipts
to 009. No general PAM configuration campaign is authorized.
