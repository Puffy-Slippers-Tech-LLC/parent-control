# F06 — Qualify Fedora fixture provisioning

Acceptance: installed
Targets: onpc-Fedora44
Requires: F05

## Purpose and scope

Deliver Fedora support in the same
[provisioning implementation](../Fixture-Design.md#owned-ssh-provisioning-and-readiness),
including enforcing SELinux, native file-trust metadata and the exact admission
needed by deliberately untrusted controls. No duplicate Fedora transfer engine.

## Read and implement

Read F01's Fedora closure/ABI inventory, F05's complete call chain,
`tests/fixtures/native_assets.py` / `native_trust.py`,
`tests/integration/baseline_fixtures.py` native policy/backend functions,
`baseline_guest.label_preparation` and applicable Fedora fixture/trust regressions.
Keep generic causes in shared code and isolate platform activation/labels.
Preserve native vendor trust, rule precedence and product policy bytes.

## Finite validation and cleanup

Register/list the planned Fedora engineering binding. Run its affected isolated
safety tests, then a watched owned Fedora history for first/minimal transfer,
repeat/no writes, update, interrupted transfer/activation and exact recovery.
Include F15's larger→smaller→disjoint history, modified-removal refusal, retained
shared members and absence of removed native admission. Prove loaded fixture-only
barrier coverage against launch/fork/runtime-open races, C/Python quiescence and
unknown-owner refusal without changing product rules or SELinux enforcement.
Observe correctly labelled runtime use, exact loaded native trust and distinct
untrusted controls under enforcing SELinux; broad directory trust or disabled
enforcement fails. Wrong-role/foreign-file refusals preserve unrelated bytes.
Independently verify final metadata/receipt, release pins and restore only owned
state after F50's per-permission barrier-removal witnesses pass and all nonce
probe executables/descendants and observer sources are retired. Cover attributed
trust=0/1 decisions, wrong/stale log attribution, partial parse, permissive or
changed daemon, overflow denial and delayed observer removal/PID reuse. Prove
F33's entire legacy movable set is retired outside the selected subset, with
original source copies removed and environmental settings preserved.
Cover lost replies during
removal, trust activation and barrier release before declaring readiness. Shared
revisions renew affected Ubuntu fixture-infrastructure proof before close-out.
No product behavior assertion is required. Update the
delivered target inventory and guides; use the [master](../Fixture-Execution-Plan.md).
