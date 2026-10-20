# R01b — Choose the effective authentication policy

Acceptance: review

Required tasks: R01a — selected execution/activation boundary.
Estimate: 15–30 minutes.

Read the [master](../Kiosk-Resilience-Plan.md),
[account boundary](../SystemDesign/Kiosk-Confinement.md#admission-and-account-integrity),
[architecture decisions](../SystemDesign/Kiosk-Confinement.md#architecture-decisions-required-before-the-entry-proof)
and [execution contract](../Execution-Plans.md#execution-and-delegation).

## Session boundary and deliverable

Extract effective PAM/passwordless policy from R01; approval lifetime belongs to
R01c and account-field ownership to R01d. Trace the real PAM/authselect, login-check
and packaging policy callers, including account/access, empty-token, open/close
and setcred behavior. Separate effective administrator denial from unfamiliar
module names, optional callbacks and harmless byte/formatting differences.

Choose a kiosk-scoped passwordless route preserving explicit administrator
access/expiry policy and ordinary child/admin authentication. Never enable global
null-token authentication. Define how an unfamiliar benign session callback
remains compatible without a name exception. Preserve genuine selected-parent
authentication, including Fedora's privileged helper; blanket no-new-privileges
or nosuid assumptions cannot disable it.

## Acceptance and close-out

Record the concrete cross-platform mechanism/source basis and scoped rejection
decisions in the existing design/ledger, with effective-denial negatives and
ordinary-role/permitted controls. Specify R02b's unfamiliar-callback proof and
R07's remaining valid-variation scope. R01 integrates/reviews this decision;
this task changes no product policy or test expectation. Check links and
documentation consistency; retain historical evidence and no runtime state.
