# 008 — Implement authentication-policy validation

Acceptance: host

Session boundary: implement only 008a's settled supported/refused branches and
their parsing/composition/rollback and closed diagnostic checks. Reuse its
effective-policy investigation. Unresolved behavior remains a decision-contract
blocker; it is not another investigation to absorb into this implementation row.

Read the [master](../Kiosk-Prompt.md), effective Ubuntu/Fedora authentication
configuration, package provisioning/PAM adapters, `empty_authentication_probe()`
and complete affected policy validation tests. This is a separate audited
hypothesis, not the root cause of the recorded directory-layout incident.

Implement 008a's supported/refused contract for administrator policy that disallows
empty tokens, including Fedora `without-nullok` and Ubuntu's effective GDM auth
stack. Preserve administrator authentication policy and ordinary accounts. Do not
enable null tokens, weaken authentication or conceal an incompatibility merely
to prevent a password prompt. Use existing package quarantine/refusal mechanisms
for genuinely unsupported configuration and expose a closed diagnostic reason.

Add only missing finite host parsing/composition/rollback cases and update the
owning lifecycle/support contract if clarification is required. Ambiguous product
behavior follows the regression decision contract, not a changed expectation.
Run affected maintained host checks and build after any packaged change.
Declare the precise installed variants and expected results for 009; close only
this host row after its contract and code agree.
