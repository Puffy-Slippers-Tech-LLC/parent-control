# C08 — Protect child-controlled consumed inputs

Acceptance: host

Required tasks: C08a.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Use C06's actual-consumer map for fixed entrypoints, environment/search
selection and startup/settings inputs the child can really write. Implement
only missing narrow exclusions. Trusted installed Python/GTK/GI/native libraries
and lazy loading remain usable.

Retain relevant group/ACL positives where they prove actual access; unfamiliar
files, readable scripts or broad mode-bit differences are not sufficient
refusal reasons. No custom ACL/NSS/loader framework, private runtime image or
global inventory. Optional input/action failure leaves core use working.

Port focused behavior tests and finite installed input/normal-use bindings.
Verify cumulative C08a controls, update the defense map and apply independent
review plus final build.
