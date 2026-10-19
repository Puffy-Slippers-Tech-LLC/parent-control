# 009 — Qualify Fedora authentication policy

Acceptance: installed
Targets: onpc-Fedora44

Session boundary: qualify 009a's canonical policy history on Fedora and
reconcile both candidate receipts. Session exception: effective incompatible
policy, refusal, exact restoration, ordinary-account control and public reentry
stay together. 009a retains Ubuntu acceptance; rerun it after invalidating fixes.

Use the [master](../Kiosk-Prompt.md), 008's supported/refused contract and existing
PAM environment/first-configuration mechanics. Inspect current native policy
before declaring a fixture effective; package names alone are not evidence.

On Fedora, prove supported empty-token authentication and usable public kiosk
entry, then exercise the finite incompatible-policy branch selected in 008.
Require its intended configuration/admission refusal and sanitized reason,
preserve ordinary-account authentication and never override administrator policy.
Record actual greeter behavior only when the fixture legitimately reaches GDM.

Restore exact owned authentication state and require fresh successful public
entry. Keep refusal/restoration/recovery together, retaining package/PAM identities
and first-failure evidence. Extend the existing canonical PAM owner and register
the selector rather than create another auth harness. Require Fedora acceptance,
a still-valid 009a Ubuntu receipt and owned cleanup before close-out; no general
PAM configuration matrix is added.
