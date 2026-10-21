# 315 — Read kiosk What's New and return to the request

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).

Estimate: 20–30 minutes. This planned general feature scenario has no assigned
case ID or executable and is not a kiosk confinement baseline prerequisite.

## Scope and prerequisites

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **185k** — Installed restricted About and unchanged request return.
- **014** — Prepared kiosk request with independently captured choices.

Customer goal: read the installed release information and resume an unchanged
usable request. This preserves the new What's New coverage removed from C04i;
About identification already belongs to case 192 and is not a second journey here.

## Implementation and acceptance

Read `tests/e2e/kiosk_about.py`, shared information operations in `accessible_ui.py`,
the public-ID inventory in [Application UI API](../Application-UI-API.md), and the
packaged information source via [Front ends](../../SystemDesign/Frontends.md).
Use shared public API operations; no external navigation, translation sync or
visual comparison. Extend only missing content/readback operations.

Prepare and capture the normal Riley/Jamie/75-second/soft-included request.
Open What's New; independently read meaningful content matching the installed
package's latest release; close normally and require the same usable request.
Grant no time and change no policy. About need not be reopened to consume its
shared information/return mechanics.

Assign one new stable case, finite recipe and complete worker binding during
implementation; insert a bounded prerequisite for any missing independent API
qualification. The selector is unassigned and no ready case is claimed. Run
affected host checks and installed acceptance with finite timeouts, preserve
package/content identity and owned cleanup, then regenerate coverage after pass.
