# 048e — Choose valid overlay values and Cancel

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **REQUEST04/05/06/08 overlay valid choices and REQUEST11/12 Cancel**. Named consumer: task **048a** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048** — DESK12, REQUEST02 direct entry, REQUEST13 panel entry and REQUEST03 readback.
- **014** — FLOW04 kiosk.
- **047** — APP04; FLOW08 native usable-app scope.

## Implementation

Bind fixed-child overlay approver/duration/custom/soft-app values and independent estimates. Reuse shared kiosk operations with overlay IDs, and bind Cancel back to the earlier child activity.

Read only the selected REQUEST rows and
[shared form contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form),
the [native fixture boundary](../E2E-Building-Blocks.md#native-fixture-preparation),
FLOW08 and the [composition preflight](../E2E-Building-Blocks.md#composition-preflight).
Current implementation is the declarative
[`overlay_valid_choices.py`](../../../tests/e2e/overlay_valid_choices.py) qualification,
using `journey_blocks.overlay_entry`, `native_usable_app(child='child')`,
`KioskRequestJourney`, shared `AccessibleUI` choice/Cancel operations, and
`onpc_request_flow.overlay_valid_choices`. Host checks are
[`test_e2e_overlay_valid_choices.py`](../../../tests/unit/test_e2e_overlay_valid_choices.py)
and the native GTK overlay adapter check in
[`test_request_form_component.py`](../../../tests/ui/test_request_form_component.py).

The fixed slice publicly sets Riley's daily allowance to 900 seconds, signs in
as Riley, and captures the owned native window and edited draft. It selects
Jamie, 300 seconds, custom `1.25` minutes (75 seconds), rest-of-day and both
soft-app states. Estimate bounds come from the independent Parent balance and
elapsed time. Both Cancel results must preserve the original activity exactly.
An independent command entry reads the saved zero-duration/Jamie/excluded choice,
then selects 300 seconds and Cancels. This is remembered form state, not a new
default or a FLOW04 qualification. Escape, invalid input and full local choice
matrices remain with their owning tasks.

## Live VM acceptance

With usable child time, capture app activity, open the overlay, edit each valid choice and read it back. Cancel and require the same usable activity. Reject child reselection and wrong-surface input.

Qualification selector:

```sh
tools/run-tests integration check_e2e_overlay_valid_choices
```

Affected live regressions after that qualification passes: `check_e2e_kiosk_valid_duration`
(shared duration/estimate input), `check_e2e_kiosk_eligible_choices` (account guard),
`check_e2e_request_exit` (shared Cancel), `check_e2e_native_app` (default native
account binding), and `check_e2e_shell_panel` (unchanged entry defaults).
Run these through `tools/run-tests integration` without `--vm`. Stop on the first
live failure under this session's handoff boundary; retain the unchecked row and
pointer until all required live results and cleanup pass.
