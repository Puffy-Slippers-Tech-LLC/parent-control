# C07t — Protect standalone terminal and TTY access

Acceptance: host

Required tasks: C06.
Estimate: 20–30 min.

Apply the [remaining-plan task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract).

## Session boundary and deliverable

Use C06a/C06's finite standalone terminal/TTY and non-desktop shortcut map and
actual account/PAM/action callers. Add only missing justified barriers while
preserving passwordless request-only entry and ordinary-account terminal/TTY
use. Preserve the existing local graphical desktop barriers in the confinement design.

Pair every defense with targeted host negatives, normal-use positives and exact
installed bindings for C11t/C12t. Already effective barriers need proof, not
duplicate code. Preserve original assertions split from former combined local
desktop/TTY tasks, case identities, timeouts and restoration. Run affected tests,
required independent product/backend review and final packaged-input build.
