# Task 20 — guarded reboot observation, local verification

Result: the missing old-boot/readiness distinction is implemented and locally
verified. No live reboot, customer scenario or new installation qualification
was attempted. Task 20 and E2E-002 remain pending. The all-task VM clearance
persists; implementation readiness, not a VM hold, bounds this slice.

The [owning E2E contract](../../../tests/e2e/README.md#customer-reboot-observation-boundary),
[transport contract](../../../tests/integration/README.md#reusable-implementation-contracts)
and [reuse map](../Reuse-Map.md#installation-helper-and-open-limits) describe
the supported interface and its limits. `Transport.wait_boot_change` reuses
the existing readiness loop. `ReadOnlyObservations.wait_boot_change` requires
an observed starting boot, changed readiness identity and a fresh agreeing boot
read. It latches failure and exposes no reboot command or observer reset.
The boot hash program moved unchanged to the transport's shared constant.
Ordinary E2E-001 and the existing system reboot method retain their behavior.

## Verification

All checks exited zero, with no failed or skipped test cases:

| Check | Result |
| --- | --- |
| `tools/run-unit-tests tests/unit/test_vm_transport.py tests/unit/test_e2e_observation_transport.py tests/unit/test_e2e_installation_boundary.py -q` | 1,329 passed, 1.29s |
| `tools/run-unit-tests tests/unit/test_graphical_smoke.py tests/unit/test_graphical_smoke_cleanup_safety.py tests/unit/test_e2e_controller_qualification_cleanup_safety.py tests/unit/test_e2e_worker_cleanup_safety.py tests/unit/test_support_architecture.py -q` | 423 passed, 1.04s |
| `make check` | 5,228 unit/contracts passed in 100.27s; 17 private-D-Bus components passed in 0.38s; stage traceability and syntax/source guards passed |

`test_customer_reboot_uses_real_readiness_loop_and_revalidates_final_boot`
exercises the actual observer/transport composition with controlled SSH outputs.
Transport cases distinguish old-boot success and status 255 from terminal guest
failure, malformed data, configuration replacement, ownership loss and timeout.
Observer cases cover stale/unobserved identity, a second reboot, interruption,
final-read failure, redaction and refusal of all later reads/waits. The existing
kernel-probe test executes the shared program and compares its actual digest.
These are host tests with controlled transport responses, not VM proof.

No test failed. A documentation patch initially failed context validation and
was reapplied with corrected context; no partial edit or recovery remains.
Initial source reads used several nonexistent inferred filenames; subsequent
discovery located `vm_transport.py` and `graphical_lease.py`. No permission or
Polkit action was denied. No privileged operation or installation was requested.

## Tested inputs and cleanup

Base revision: `944da18980cab1181c287ba9d59e88276cbea654`; initially clean checkout.
These source/test digests describe the verified local edits:

| Path | SHA-256 |
| --- | --- |
| `tests/integration/vm_transport.py` | `4a839f21838cfffa7096961999a62da69afb9bb1624d03b26e4522bf914ef85d` |
| `tests/e2e/guest_observations.py` | `5e8d4e9d3023bda0f349bcc7b6c04c079ac0036bfd08b04fc0f1d32bd6894e39` |
| `tests/e2e/observation_transport.py` | `aefbaaba528e5f03991104248489629a081fd9eed86606e4e3665547ef087106` |
| `tests/unit/test_vm_transport.py` | `38b641bbbb7cb91c7ebae8881ca480aacf05a116c4dd7f37222fad371767c4a4` |
| `tests/unit/test_e2e_observation_transport.py` | `541e048b3d9476f08f4b2c8865af79429396d5faba2d0a476e42c5c77bacb6e3` |

All started commands exited and results were collected. No VM lease, worker,
display, serial stream, screenshot export or retained recovery resource was
created by this slice; no current VM-state claim is inferred from old evidence.
Documentation changed after code verification; fresh source-bound package
artifacts remain necessary before the next VM attempt. No launcher/control-state
changes were made. Actual settings: `gpt-6-astra` / `high`, Standard processing.

Next: connect ordered installation-only customer reboot input and acknowledgements
to this observer, cover the serial/display ownership transition locally, build
fresh artifacts, run isolated safety prerequisites and perform one guarded live
proof. Existing authenticated installation and refusal evidence stays retained;
the intermittent recipient failure remains unresolved. Full Task 20 estimates
remain Unknown because the real cross-boot/readiness/fault work is unmeasured.
