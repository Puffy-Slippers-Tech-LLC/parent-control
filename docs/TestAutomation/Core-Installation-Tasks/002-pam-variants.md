# 002 — Exercise native PAM environment variants

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

## Purpose and finite scope

Add native environment variety around the successful task 001. At handoff only
host parsing/composition covers the full variant set. Add one maintained
parameterized engineering history with these finite inputs:

- Plain supported vendor stack, retaining all mandatory security modules.
- Ubuntu's reviewed optional LXC session profile; Fedora's supported vendor/SSSD
  include layout, without installing an unsupported cross-distro module.
- A pre-existing administrator override of `systemd-user`, preserving its exact
  original bytes after product removal; do not overwrite distro ownership.
- A pending vendor PAM update requiring safe refusal, preserved policy/exclusion
  and successful normal retry after an owned resolution.

The optional module is a reusable baseline prerequisite. Deliberate profile and
override changes are bounded scenario mutations with before/after evidence;
never remove mandatory PAM gates to manufacture a plain variant.

## Reading and implementation route

Use the [master](../Core-Installation-Coverage-Handoff.md),
[Lifecycle](../../SystemDesign/Lifecycle.md),
[Kiosk Confinement](../../SystemDesign/Kiosk-Confinement.md),
[coverage maintenance](../../../tests/README.md#core-installation-and-runtime-compatibility),
[VM mandate](../../Mandates/VM-Mandate.MD), installed runner/environment and
[shared support](../../../tests/support/README.md).
Inspect `test_kiosk_confinement`, `test_package_configuration`,
`system_first_configure`, `system_kiosk_accounts` and registered removal histories
before choosing their existing mechanics. Cases own finite inputs/assertions;
shared modules own reusable ownership, transport and recovery.

Planned selector: `test_pam_environment_installation_variants` (unimplemented).
Register its complete phases and persistent case IDs in the existing system
runner before execution. Do not add an ad hoc guest script or another installer.
Review all applicable scheduling/resource inventories for new host tests.

## Validation, expected results and cleanup

Run affected host regressions through `tools/run-tests`, then the registered
variant history on both targets through `tools/run-tests system`. Every variant
must name its actual effective stack, prove ordinary-user preservation and safe
kiosk admission, and preserve existing saved policy. Successful configurations
must reach broker activation and enforced native execution after the required
reboot. The vendor-conflict case must fail before release/activation and succeed
on repaired-input retry. Removal must restore the pre-existing override exactly.

Keep each variant's install/failure/retry/reboot/removal observations in one owned
history; do not restore snapshots midway. Use existing cleanup and retain its
result on both targets. Run `make build` for product/build-input edits, refresh
generated coverage and Markdown links, record exact variant reports, close this
row and advance the master's pointer. Missing native evidence remains a blocker.
