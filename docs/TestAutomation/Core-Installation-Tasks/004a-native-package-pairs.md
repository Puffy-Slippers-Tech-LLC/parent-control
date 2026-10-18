# 004a — Select finite native dependency package pairs

Acceptance: review

Requires: 003.

## Scope and route

Resolve the first missing prerequisite for
[004](004-native-dependency-update.md): an obtainable, supported old/new native
package pair per distro that changes an executable/PAM input measured by the
product. Read the [confinement update contract](../../SystemDesign/Kiosk-Confinement.md#installation-updates-and-removal),
native inventory/replacement/reexec/loader functions in
`tests/integration/system_kiosk_confinement.py`,
[installed environment](../../../tests/integration/Environment.md), and the
[baseline boundary](../../Mandates/VM-Mandate.MD#vm-host-setup-and-baseline).
Inspect the existing builder before proposing its extension; released product
pairs in `tools/build_test_artifacts.py` do not supply native dependency pairs.

Use authoritative distro metadata/artifacts to identify a finite transaction
closure for each target: repository origin, signatures/native verification,
versions/architecture/package digests, dependencies and exact changed measured
files. Verify availability and compatible old/new installation on the supported
distro; document an unknown as unresolved, not as qualification. No VM mutation
or package transaction belongs to this review task.

## Acceptance and close-out

Record the selected identities and authoritative sources in the existing 004b
brief, with exact preconditions for preparing the old generation before product
admission. Establish the finite expected results for retained mappings,
enforcement, fresh admission refusal, loader exclusion, reexec/retirement and
activation/reboot from the owning product contract; do not assume an ordinary
native update automatically publishes a new product generation. Identify which
native scripts/triggers must run and which independent evidence proves them.

The pair must change measured bytes under a real native transaction; identical
reinstall, synthetic replacement and an unbounded online update do not qualify.
If either supported pair or safe dependency closure is unavailable, leave this
row unchecked and record its exact missing identity and return condition. Do not
substitute another distro/version or weaken 004. Check links/plan; mark only
004a complete when both finite input plans and expected results are resolved.
