# U05 — Restore entry after interrupted configuration

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: U04.
Estimate: 45–90 min; session exception: one owned configuration interruption/retry/reentry history.

Apply the [master contract](../Kiosk-Usability-Plan.md#per-task-acceptance-boundary).
Read [owned migration](../SystemDesign/Lifecycle.md#prepared-owned-lifecycle-migration),
the expiry/provenance limitation under
[provisioning](../SystemDesign/Lifecycle.md#kiosk-provisioning-and-selected-session),
`packaging/lifecycle_migration.py`, distro PAM and `tools/provision.py` callers.
Reuse existing configuration-interruption cases and supported installation entry.

Choose one interruption after owned quarantine but before release. Verify safe
refusal while incomplete, then repair any demonstrated failure of supported
configuration retry to restore usable entry after dependencies recover. Preserve
the original expiry, UID/home authority, administrator denials and live/foreign
state. Do not infer writer provenance from an expiry value alone; if recovery
is ambiguous, retain safe refusal and an actionable diagnostic rather than
silently clearing an administrator restriction.

One complete installed interruption/retry history per target is enough; no
phase-by-phase crash matrix or uninstall/purge campaign. After supported recovery,
observe the master's bounded entry/use/reentry control without manual product
state deletion. Run affected tests, backend review/build and owned cleanup;
close only U05 when the selected interruption recovers. If ambiguous provenance
prevents that recovery, leave U05 unchecked with the exact blocker and return
condition. Record unrelated provenance limitations without claiming to fix them
or expanding into a general account-policy redesign.
