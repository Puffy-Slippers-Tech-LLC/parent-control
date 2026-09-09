# Task 20 startup enforcement observation

Task 20 remains earliest ready and unaccepted; no earlier entry is bypassed.
Actual settings: `gpt-6-astra` / `high`, Standard. This bounded slice adds
fapolicyd/GDM ordering evidence and safe final-provenance diagnosis over the
existing installation controller. Existing edits were preserved.

## Result and reusable boundary

The [owning startup contract](../../../tests/e2e/README.md#startup-enforcement-observation)
records the fixed guest program, decoder, systemd interface, boot correlation,
regressions, downstream consumers and qualification limits. Systemd's exact
completed canary command and its monotonic execution timestamps supply the
missing evidence beyond `is-active`. No service or product policy was changed.
Journal receipt timestamps were rejected during design because delayed logging
cannot safely order helper completion against systemd activation.

The successful installation's GDM acknowledgement now refuses failed, stale,
replaced or out-of-order startup evidence. It remains distinct from the reviewed
graphical match. The current activation pair is observed; complete earlier-boot
history and continuous enforcement are not claimed. The E2E-028 fault cases
remain independently required.

The [provenance contract](../../../tests/e2e/README.md#controller-owned-provenance)
now documents fixed early/late final refusal retention. Unknown exception text
is never exported; source/asset/baseline diagnoses are preserved when supplied
by `VerifiedInputs`. The previous live final refusal's cause remains unknown;
this slice does not relabel it or establish live success.

Broker publication ordering requires separate work: `Service.__init__` performs
execution-policy synchronization, extension refresh and best-effort cap cleanup
before `register`; `configure_broker_logging` installs only the daily-file handler.
There is no existing correlated journal trace of these phases. Do not infer
ordering from a post-start introspection response or make GDM depend on broker
readiness. Read the [startup audit](20-Startup-Audit-20260908.md) and
[lifecycle contract](../../SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle)
for that next boundary.

## Verification

- `tools/run-unit-tests tests/unit/test_e2e_startup_observations.py tests/unit/test_e2e_observation_transport.py tests/unit/test_graphical_smoke.py tests/unit/test_graphical_smoke_cleanup_safety.py tests/unit/test_e2e_provenance.py -q`:
  1,478 passed, first handle 81468 and corrected-code handle 74547.
- Review found that the initial probe stripped the boot-id newline while
  `BOOT_SHA256_PROBE` hashes it. The realistic kernel-file regression
  `test_actual_guest_program_correlates_current_boot_units_and_completed_canary[None-None]`
  reproduced that mismatch (one failed, 40 passed, exit 1). The probe now hashes
  identical bytes; the test also executes the canonical reboot program and
  compares their results. Its module passed all 41 cases after correction,
  including real `GLib.Variant` decoding of the documented systemd reply.
- `test_final_provenance_keeps_safe_specific_cause_through_cleanup` covers
  16 early/late cases, preserved original exceptions, terminal failed status,
  redaction and one lease cleanup/release. Existing safety coverage also passes.
- Initial `make check` (handle 29987) passed 5,667 unit/contracts and 17 private-bus
  components, exit 0. It preceded the boot-byte correction and is superseded by
  final `make check` (handle 3167): 5,667 unit/contracts in 104.34s and 17
  components in 0.34s, exit 0, including stage traceability and syntax/source
  checks. No checkout edits occurred during either run. Later edits only record
  results. Changed shared documents passed 134 link checks; final handoff links
  and scoped whitespace checks also passed.

Final code identities (SHA256; focused and full checks used these bytes):

| File | SHA256 |
| --- | --- |
| `tests/e2e/startup_observations.py` | `ef96bc8dccab53160c9e801f92612cf035cc9f2d7de6767c53dd06f404b4048a` |
| `tests/e2e/provenance.py` | `0df11f75858624070020d9d8e4f67fbb6544225afd15049eeea6d29ec7f2dcce` |
| `tests/e2e/observation_transport.py` | `df47c4d31797a0e9de5a1d8aadf82b2181b6a7bd9e732d7ef4eaec011b818c07` |
| `tests/integration/check_graphical_smoke.py` | `5a70d85504e59b5402996f9392f5adcc5870debb5dcb0153cae1ec65c90b9c61` |
| `tests/unit/test_e2e_startup_observations.py` | `24c7f1e768ab84d35a2b35533bcaf5f38b84af65bb6839afeb4989a9eb8381e8` |
| `tests/unit/test_graphical_smoke.py` | `01f6e320aabd5ea807a617c836afbc19ccb126e003b75511bc47b47348674571` |
| `tests/unit/test_graphical_smoke_cleanup_safety.py` | `a0721e73e0728a5c40b9cb41262c42485e796d86ba53eea885a0883a097c9e1e` |

No package build, guarded VM attempt, VM lease, screenshot export or guest
mutation was started. Broker ordering and remaining complete-journey observations
must be implemented before the next meaningful full installation attempt;
the all-task VM clearance remains effective. Attempt counts stay at 21 overall
(three historical passes, eighteen failures). No new approval/Polkit denial or
recovery operation occurred. All started commands exited and results were
collected; no owned resource or cleanup obligation remains. Test-tool
activation is `none`; no product integration or data migration changed.
