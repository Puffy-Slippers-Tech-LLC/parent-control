# R02 — Build the minimal entry proof

Acceptance: host

Requires R01. Read the [master](../Kiosk-Resilience-Plan.md#acceptance), R01's
accepted design/ledger and complete affected native, policy, session and packaging
functions. Use the [test map](../TestAutomation/README.md) to locate maintained
fixture, resource and UI contracts before changing supporting operations.

## Deliverable

Implement the smallest runnable slice of the intended production entry route:
owned account, dedicated session, the actual execution boundary, request form,
real parent-approval path, exit/reentry and one bounded owned renewal. It must
already tolerate an unrelated host-layout change and a missing cosmetic resource.
Use the same components that later production integration will retain; create no
second sandbox engine, general remote-control API or unconfined fallback.

Reuse existing private PAM/native probes and installed/public station operations.
Record a finite selector/input map for R03/R04 when those selectors actually
exist; do not label a planned name runnable. Observe actual GDM and manager
credential ordering, enforcing policy, first exec, relevant service launches and
PAM teardown. Cover explicit alternate desktop/SSH and reachable external-launch
attempts with working permitted controls.

This is a bounded architecture proof, not full compatibility implementation.
Keep predecessor code only as needed until R05 integrates and deletes it; the
candidate route cannot silently fall back to unrestricted execution or claim
success from the old broad admission path.

## Validation and close-out

Run affected native/PAM/preparation/session/package host selections through the
maintained launcher, including actual production-call composition and owned
failure cleanup. Apply resource review to changed fixtures. Require the master's
product review, then `make build` after the final packaged edit.

Record exact candidate, selectors, expected public results and test-double limits
for both target briefs. Complete owned cleanup. Host success closes only R02;
R03/R04 must demonstrate that this smaller route works on actual systems before
broader production work. Session exception: keep this one native transaction and
its caller/cleanup proof together.
