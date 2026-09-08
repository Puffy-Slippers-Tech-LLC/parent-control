# Task 20 installation/startup declaration audit

Scope: declaration and capability audit on the authorized dev/host machine;
`gpt-6-astra` / `high`, pinned by the slice launcher. Task 19B is accepted;
Task 20 is the earliest unchecked entry, with no bypass. The all-task VM
clearance remains effective. No live VM attempt was started in this slice:
the three product cases lack executable callbacks and correctly remain pending.

## Finite Task 20 case list

| Case | Contract and risk | Required independent evidence |
| --- | --- | --- |
| `E2E-002/clean` | `ONPC-CORE-INSTALL-001`, `ONPC-COMP-BROKER-010`; hidden preinstallation, ineffective reboot or premature readiness | Product absent, exact package installed through authenticated customer terminal, private output and visible reboot notice, product-created reboot marker, actual reboot with changed boot identity, installed layout, broker publication ordering, fapolicyd canary/startup ordering and usable GDM. Preserve existing accounts/unrelated settings; reboot intentionally ends sessions. |
| `E2E-028/startup-enforcement` | `ONPC-COMP-BROKER-010`; GDM exposed before live enforcement | Retained stable ID now explicitly owns fapolicyd readiness failure. Observe failed readiness and denied managed GDM startup before removing the fault; recover and verify usable GDM in the same attempt. |
| `E2E-028/startup-broker` | `ONPC-COMP-BROKER-010`; broker operations exposed after failed reconciliation | Added independent execution-policy reconciliation fault. Prove its D-Bus object remains unpublished and Parent operations unavailable; separately establish the healthy fapolicyd gate. Recover and verify broker operation in the same attempt. GDM is not specified to depend on broker readiness. |

The [lifecycle contract](../../SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle)
also requires extension activation before publication; stale-session-cap cleanup
is explicitly best-effort. Do not turn that tolerated cleanup exception into a
startup failure requirement. One failed dependency per fault attempt avoids
masking the other gate. Other owners retain their E2E-028 variants; the shared
declaration now requires visible/backend failure evidence before recovery.

The new [installation requirement](../../Specification.md#installation-and-startup)
formalizes existing Task 20 acceptance, closing E2E-002's requirement gap.
`tests/requirements.json` retains planned coverage and no invented executable
references. Inventory totals: 33 families, 157 variants, 156 pending; no new
case is runnable or accepted.

## Reuse and next missing capability

- `tests/e2e/asset_transfer.py:AssetTransfer.provision` supplies digest-verified
  package/fixtures only while the leased guest is off in setup; it never installs.
- `tests/e2e/controller_qualification.py:execute` supplies the ordered recorder
  pattern; its smoke requires one unchanged boot, so it is not an installation
  callback. Preserve accepted smoke behavior.
- `tests/integration/graphical_smoke/lib/onpc_serial.pm:run` supports real fixture
  login and a fixed read-only command. It lacks authenticated package installation,
  reboot input, reconnect and post-reboot evidence. Its password proof validates
  the stock login process, not a sudo prompt; do not reuse it as sudo proof.
- `tests/e2e/observation_transport.py:ReadOnlyObservations.read` exposes fixed read-only
  probes. Boot digest and assets exist; package absence/installation, marker and
  readiness ordering probes are missing. Keep installation out of that API.
- `tests/system/test_install_smoke.py` supplies installed-package, reboot-marker
  and changed-boot assertions through `system_guest`; reuse their contract after
  inspecting that helper's guard, without running guest tests on this host.

Next bounded implementation: add the fixed authenticated terminal-install
boundary and its independent package-absence/result observations, reusing the
worker and asset transfer. Cover secret/no-echo denial and fixed-command/phase
refusals locally before a guarded live proof. Then extend the same journey with
actual reboot, reconnection and startup ordering; fault controls remain separate.
Do not register a partial installation as a ready complete E2E-002 journey.

## Verification and cleanup

Verification results are recorded in the [active handoff](../Task-20.md#task-20-continuation--2026-09-08).
No expensive attempts, new denial, VM lease, guest process, screenshot export or
recovery operation was created. Existing unrelated edits were preserved.
Remaining task estimates are Unknown: three concrete cases are identified,
but install/authentication, reboot/reconnect and fault-control gaps have no
measured implementation or live-attempt duration yet.
