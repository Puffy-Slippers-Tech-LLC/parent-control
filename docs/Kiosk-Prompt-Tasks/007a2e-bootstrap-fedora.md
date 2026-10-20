# 007a2e — Qualify corrected native bootstrap on Fedora

Acceptance: installed
Targets: onpc-Fedora44

Requires 007a2b, 007a2c, 007a2d. Estimate: 20–30 min.
Staged prerequisite of [007a2](007a2-ambient-ubuntu.md). Activate only through
the master's [smaller-slices route](../Kiosk-Prompt.md#smaller-execution-slices)
when that consumer is selected. Preserve existing queue order and acceptance.

## Purpose and reading route

Qualify the same cumulative native/helper correction under actual enforcing
SELinux, including the real pre-PAM GDM caller context. Read
[007a2d](007a2d-bootstrap-ubuntu.md) and its complete owning-contract/source
route, [007a2b](../Kiosk-Prompt.md#helper-private-creation--007a2b), the
[original entry checkpoint](../Kiosk-Prompt.md#ubuntu-retained-ambient-checkpoint--007a2),
and [Fedora bootstrap history](../Kiosk-Prompt.md#fedora-native-bootstrap--006e3).
Older root-group bootstrap passes do not establish corrected caller acceptance;
retain their failures, observations and explicit evidence limits.

Read the [VM mandate](../Mandates/VM-Mandate.MD) before operations. Reuse its
registered-target authority, leases, watch, guarded transport and owned cleanup;
installation uses only `make install` through maintained preparation, never on
the development host. Confirm registered case 292 in
`tests/integration/system_case_ids.py`, its callable in
`tests/system/test_enforcement.py`, the
[catalogue](../../tests/integration/README.md), and complete `first_exec()`,
`verify_bootstrap_permissions()` and witness callees in
`tests/integration/system_kiosk_confinement.py`. Run:

```sh
tools/run-tests system --vm 'onpc-Fedora44' --id 292
```

Keep maintained explicit deadlines/timeouts and enforcing SELinux. This bounded
engineering qualification grants no public request-form or 293/294 acceptance.

## Finite acceptance and close-out

Bind exact package/native/helper/frozen inputs to Ubuntu's cumulative candidate,
with platform-specific package, config, policy and attestation identities retained.
Require all six original bootstrap assertion families on Fedora:

1. Independent package/boot/config/loaded-policy/attestation/native/input binding.
2. Actual `init_t` fresh manager and `xdm_t` retained gate PAM. Record pre-PAM
   euid/fsuid/egid/fsgid and umask ordering; independently prove actual nonzero
   filesystem GID with root filesystem UID for GDM, preserving the distinct
   manager context and caller credentials/umask.
3. Independent read-only root clone, proc/task/starttime/pidfd/namespace,
   required-source inode and recursive read-only proofs, original absolute
   deadline and unchanged original manager/view identity.
4. Both copied systemd and systemd-executor ELFs through both manager entrypoints.
5. Live notify-reload reexec, allowed service, exact fresh enforcing shell and
   unconfined denials, and write/namespace/escape restrictions.
6. Caller/setup FD ownership, unchanged policy/PAM and ordinary-account contexts.

Keep host SGID-parent, distinct effective/filesystem-GID and restrictive-umask
(including 0777) controls as bounded supporting evidence from 007a2b. Do not
claim that metadata doubles, single-GID namespaces or the installed baseline
prove those host corners. Repair bounded witness/preparation defects under the
owning failure contract. Independent implementation beyond this finite slice
needs a bounded prerequisite, not a source-review or host-test substitute. Any
product repair requires the master's
[Astra XHigh review and revision gate](../Kiosk-Prompt.md#astra-review-and-revision-for-every-product-fix).

Retain original failures and expected/actual results with the complete receipt.
Finish exact identity-owned manager/unit, children, descriptors, fixture and
runner cleanup, baseline audit and independently verified VM off. Compare both
receipts against final cumulative inputs; changed shared inputs require repeating
affected complete Ubuntu acceptance. Record applicability and cleanup before
accepting only this prerequisite. Public Ubuntu/Fedora 293/294 histories remain
with their existing consumers, without completion credit here.
