# Task 20 broker startup witness

Task 20 remains the earliest ready unchecked task, with no bypass. Actual
settings: `gpt-6-astra` / `high`, Standard. Existing unrelated edits were
preserved. All-task guarded VM clearance persists; this slice implements the
missing broker evidence boundary before a complete E2E-002 attempt.

## Result and contract

The [owning broker startup contract](../../../tests/e2e/README.md#broker-startup-observation)
records the product witness, current-invocation correlation, fixed observer,
regressions, read bounds, qualification limits and downstream consumers.
[Lifecycle](../../SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle)
documents product diagnostics and activation (`process-restart`, no migration).
The [reuse map](../Reuse-Map.md#installation-helper-and-open-limits) routes Task
20 and later startup/recovery consumers to those contracts.

`Service` now emits real monotonic timestamps after each mandatory startup
phase and around successful D-Bus object registration. Existing daily logging
retains invocation/PID/unique-bus-owner identity for correlation in the guest;
no account/configuration data is added. Cap-cleanup exception diagnostics retain
only the error type. Failed diagnostic writing does not fail product readiness.
A new runtime component regression replaces the brittle source-order check.

`startup-broker` observes that witness, its current systemd process/activation,
the same unique owner's actual object and an unchanged boot. It is required
alongside fapolicyd proof in installation's final GDM acknowledgement. The
static broker can legitimately be inactive at GDM: one normal read-only D-Bus
introspection request activates it; all subsequent calls forbid activation of
a replacement. This preserves independence from the fapolicyd/GDM startup gate.
The existing requirement mapping now references the component regression and
stays planned; no partial journey is marked ready.

## Verification and failures

- `tools/run-tests component tests/component/test_broker_startup.py -q`
  (handle 98634): isolated safety prerequisites passed 562 cases and three
  subtests, then all eight real private-bus startup cases passed, exit 0.
  They cover policy/extension refusal, tolerated cap failure, failed registration,
  failed log writing, absent/invalid invocation context and live object calls.
- The first focused six-module unit run (9574) failed eight cases and passed
  1,471. The OS fixture inherited group-writable mode, unlike the product's
  `0640` logs, so the probe correctly refused at `witness` before later cases.
  Set the fixture to actual product permissions; retain explicit non-root,
  writable and symlink refusal cases. Corrected run 2182 passed all 1,479.
- Final activation-aware six-module focused run (22745): 1,481 passed, exit 0.
  Scope includes real guest-program execution against fixed OS doubles, actual
  log files, GLib variants, safe decoding/failure latch, reboot acknowledgement
  and existing cleanup-safety regressions.
- Final `make check` (47678): 5,719 unit/contracts passed in 108.25 seconds and
  all 25 private-bus components passed in 0.48 seconds, exit 0, including stage
  traceability and syntax/source checks. Inputs remained frozen through exit;
  subsequent edits only record results and next selection. The preexisting
  negative host-preparation regression emitted its expected event-loop failure
  diagnostic and passed. Shared documentation link check: 158 targets, none
  missing; scoped whitespace checks passed.

Final code SHA256 identities (both final focused/full checks used these bytes):

| File | SHA256 |
| --- | --- |
| `broker/oh_no_parent_control/service.py` | `c2e3958a80ddb5e4e7958edec8cb981f13c2304d2e72070cf76c6df103523dae` |
| `tests/e2e/startup_observations.py` | `82c57c6769d2638aa8f05a4c1e88dfe619aaccc6c6363119b8c5c56ecf381807` |
| `tests/e2e/observation_transport.py` | `e64d77c6a2eda01909647867c40a0e5c5f11b25cc4c0cc73fd9a691e1d7dccb9` |
| `tests/integration/check_graphical_smoke.py` | `aba2c9481ff7d029c0cee13d12c6853c2574f27c283fa05974cf59cbfacd9f28` |
| `tests/component/test_broker_startup.py` | `66b7d91cb67da96134443f9046e64a90f332721455e177946f4cb33ee17529c0` |
| `tests/unit/test_e2e_broker_startup_observations.py` | `44f3364c990103fb4795ade826aff63a9a2b01cb3fdc990a106ffcdd30947aff` |
| `tests/unit/test_graphical_smoke.py` | `077ebff5170f66be35713cae8a1c2d064dad28df54b45baf9e4ca2e92ee683dd` |
| `tests/unit/test_service_contract.py` | `2c04a1d1e9c1509975a450d9cb48a07918922edd909891b89cdba5c73bba2d64` |
| `tests/requirements.json` | `5ce5b40d6d2021ee3f2948587631c4e8ebef797e2ae5f70105c98ef450dad344` |

No package build or guarded VM attempt was started. Live attempt counts remain
21 overall (three historical passes, eighteen failures). Both startup observers,
full graphical reboot acknowledgement, normal shutdown and final preservation
still need a complete current-input guarded attempt. Historical final-provenance
failure's cause remains unknown; its improved diagnostic is not yet live-qualified.
Complete installed-layout and visible-notice observations plus the E2E-002
callback remain next, followed by separately declared E2E-028 startup faults.
No new approval or Polkit denial occurred. No VM lease, guest process, screenshot
export or recovery operation was acquired; component resources use the existing
owned private-bus fixture and launcher cleanup guards.
All commands exited, results were collected and fixture cleanup completed; no
owned resource or recovery obligation remains. Task 20 is still earliest ready,
with no earlier bypass. Next settings lower the model to `gpt-5.6-sol` and keep
`high` effort, Standard: implement the remaining installed-layout observation
over existing `system_guest.installed` assertions and guarded transport.
