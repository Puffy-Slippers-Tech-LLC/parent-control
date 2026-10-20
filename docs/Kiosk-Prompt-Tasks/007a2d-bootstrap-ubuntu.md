# 007a2d — Qualify corrected native bootstrap on Ubuntu

Acceptance: installed
Targets: onpc-Ubuntu26.04

Requires 007a2b, 007a2c. Estimate: 20–30 min.
Staged prerequisite of [007a2](007a2-ambient-ubuntu.md). Activate only through
the master's [smaller-slices route](../Kiosk-Prompt.md#smaller-execution-slices)
when that consumer is selected; preparation grants no execution or completion.

## Purpose and reading route

Qualify the cumulative native/helper correction under actual enforcing AppArmor,
with GDM credentials established before PAM. Preserve the
[original Ubuntu entry and cleanup failures](../Kiosk-Prompt.md#ubuntu-retained-ambient-checkpoint--007a2)
and [historical bootstrap receipts](../Kiosk-Prompt.md#bootstrap-permission-reconciliation--006e).
Their old caller ordering cannot qualify this corrected boundary.

Read [system design](../System-Design.md), its kiosk confinement module,
[007a2b](007a2b-helper-private-creation.md), [execution](../Execution-Plans.md),
[approval](../Approval-Tools.md), [test ownership](../TestAutomation/README.md),
and applicable failure/cleanup/storage contracts. Before any VM operation read
the [VM mandate](../Mandates/VM-Mandate.MD); retain registered-target authority,
leases, watch and guarded transport. Product installation uses only `make install`
through maintained preparation. Do not install on the development host.

Read the registered 292 binding in `tests/integration/system_case_ids.py`,
`tests/system/test_enforcement.py` and the
[bootstrap catalogue](../../tests/integration/README.md), then complete
`first_exec()`, `verify_bootstrap_permissions()` and their witness callees in
`tests/integration/system_kiosk_confinement.py`. Run:

```sh
tools/run-tests system --vm 'onpc-Ubuntu26.04' --id 292
```

Preserve maintained explicit deadlines/timeouts. This is an existing engineering
selector, not a new case or a public 293/294 history.

## Finite acceptance and close-out

Bind the exact cumulative native/helper candidate, package, frozen inputs,
boot, config, loaded policy, attestation and native executables. Require all six
original bootstrap assertion families:

1. Exact independent candidate/input and loaded-policy binding.
2. Actual fresh manager and retained GDM PAM, with pre-PAM euid/fsuid/egid/fsgid
   and umask ordering recorded. Prove root filesystem UID with actual nonzero
   filesystem GID for GDM; preserve the manager's distinct real credentials.
3. Independent read-only root clone, proc/task/starttime/pidfd/namespace,
   required-source inode and recursive read-only view proofs, under the original
   absolute deadline; preserve original manager/view identity.
4. Both copied systemd and systemd-executor ELFs through both manager entrypoints.
5. Live notify-reload reexec, allowed service, fresh exact enforcing shell and
   unconfined denials, and write/namespace/escape restrictions.
6. Caller/setup FD ownership, unchanged caller credentials/umask, policy/PAM and
   ordinary-account context controls.

Host SGID-parent, distinct effective/filesystem-GID and restrictive-umask
(including 0777) controls remain required supporting evidence from 007a2b;
do not label doubles or a single-GID namespace actual installed credential proof.
Repair bounded witness/preparation defects under the owning failure contract.
Independent implementation beyond this finite slice needs a bounded prerequisite;
source review or host passes cannot replace this run. Any product repair requires
the master's [Astra XHigh review and revision gate](../Kiosk-Prompt.md#astra-review-and-revision-for-every-product-fix).

Retain first failures and expected/actual results alongside the complete receipt.
Finish identity-owned manager/unit, children, FD, fixture and runner restoration,
verify baseline audit and exact VM off. Record candidate applicability and cleanup
before accepting only this target; Fedora and public 293/294 remain required.
