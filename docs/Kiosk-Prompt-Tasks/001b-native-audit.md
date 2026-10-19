# 001b — Audit preparation and native admission

Acceptance: review

Read the [master](../Kiosk-Prompt.md), 001a's audit receipts, confinement owner
and complete affected preparation/native-binding functions and required callers.
Inspect the prior `83d502b3` change and canonical confinement/native-update tests.

Map inventory, required runtime roots and aliases, trust/layout metadata races,
attestation/enforcement, manager generation/identity, runtime ownership, recovery,
publication, binding, MAC and all bounded-helper/lock refusals. Identify each
actually consumed root; shallow sibling trust does not establish nested safety.
Record intended public results, exact current selectors and diagnostic gaps.
Limit runtime-root analysis to inputs the changed entry/private-view mechanism
actually consumes. Reuse unaffected confinement proofs; do not create a general
escape, plugin, library or desktop-service qualification campaign.

Retain the review's three alias-ancestor refusal failures: required lexical
parents and intermediate symlink targets must not become ambient omissions.
Check non-UTF-8 filenames through actual binding publication, missing required
entries, disappearing siblings, retained mounts after host replacement and
staging detach. Distinguish a test reaching attestation from a generation witness.
In particular, `verify_execution_boundary()` appends config bytes without
reattesting them, so its named stale-manager check reaches payload attestation.
`system_native_update.stale_admission()` checks the specific generation refusal;
verify its actual caller, registration and candidate-specific receipt before reuse.

Update the master's existing audit; insert only demonstrated finite gaps through
the shared plan contract. No VM mutation or product installation is part of this
review. Validate changed links, retain evidence and close only this audit slice.
