# 001 — Reconcile the entry failure map

Acceptance: review

Session boundary: audit session startup, usable-form readiness and diagnostic
projection; combine 001a's authentication/account and 001b's preparation/native
source/coverage receipts. Audit those earlier paths again only for a concrete
inconsistency. The entry failure-map obligation remains cumulative under the
master's symptom boundary; this is not a general product acceptance inventory.

Read the [master](../Kiosk-Prompt.md), [lifecycle](../SystemDesign/Lifecycle.md),
[confinement](../SystemDesign/Kiosk-Confinement.md),
[logging](../SystemDesign/Logging-and-Feedback.md#kiosk-admission-diagnostics) and
[test maintenance](../../tests/README.md#core-installation-and-runtime-compatibility).
Trace complete session startup and feedback functions/callers. Reconcile
001a/001b's provisioning, PAM, login-check and confinement findings at crossings
with this scope, including the prior `83d502b3` fix.

Verify the master's initial findings and map every shipped refusal/timeout stage
from authentication through usable form to its expected public result, sanitized
evidence and exact current selector. Include aliases, unexpected entry types,
metadata/update races, ambient generation changes, retained/failed managers,
policy/attestation loss, account metadata, package quarantine and effective PAM
authentication. Distinguish defects, missing proof, hypotheses and intentional
fail-closed behavior. Shallow tree trust is not proof about every nested runtime
input; identify which declared runtime roots can actually be consumed.
Inspect those roots where the changed entry/private-view mechanism consumes
them. Do not turn discovery into a recursive audit or expansion of every package,
plugin or desktop runtime dependency.

Update this plan's existing audit table with concrete source and coverage gaps.
Map every shipped stage to a trigger, intended public result, diagnostic
producer/collector coverage, exact canonical selector and any in-scope task. Include
post-confinement broker/readiness loss, compositor/app pre-paint exit and missing
runtime dependencies. Preserve the demonstrated lexical-alias-ancestor gap and
test non-UTF-8 filesystem names through publication; tab/newline checks alone do
not cover unrepresentable names.
Classify each entry stage as existing covered behavior, an intentional refusal,
an in-scope gap or a separate-owner observation. A stage row does not require new
acceptance if its existing proof remains valid. Do not invent speculative tasks
or accept misleading test names as coverage. An added prerequisite must pass the
master's source-dependency/symptom test and the shared plan contract.
Acceptance is a reviewed complete failure/coverage map and bounded remaining
queue, with no VM mutation, product installation or completion credit for later
tasks. Preserve current candidate edits and evidence; close only this row.
