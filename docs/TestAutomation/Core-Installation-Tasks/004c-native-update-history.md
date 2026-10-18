# 004c — Implement the retained-session transaction history

Acceptance: host

Requires: 004b.

## Scope and route

Implement one finite history for both targets using 004b's verified inputs and
the expectations resolved by 004a, preserving all
[004 requirements](004-native-dependency-update.md). Read the affected complete
`system_kiosk_confinement` inventory, `manager_boundary`, `verify_updates`,
loader/admission and lifecycle functions and their callers, plus runner phase,
selection, resume and evidence contracts. Reuse existing process identity,
transport/watch and lease owners under the
[VM mandate](../../Mandates/VM-Mandate.MD); apply
[storage](../../Mandates/Test-Storage-Mandate.md) and
[cleanup safety](../../../tests/README.md#cleanup-safety-prerequisites).

Register planned `test_native_dependency_update_retained_session` with a new
stable system ID only after checking the current inventory. Document the actual
selector, phase ordering, verified input invocation and finite timeout in the
installed runner owner and [004d brief](004d-native-update-histories.md), including
parallel target execution with the correct per-target inputs. It is unimplemented
at planning time.
Add no independent update/fault framework. Any product installation continues
through the existing `make install` recipe.

## Acceptance and close-out

Host checks must establish selection/input prerequisites, phase order, private
checkpoint binding, reboot evidence survival, resume without phase splicing,
collection on failure and owned cleanup. The history must establish old native
inputs before admission, retain an identified manager/session, perform the real
native transaction and prove changed host bytes alongside retained old mapping
identity. Require continuing enforcement, specified new admission refusal,
loader exclusion under held admission, safe reexec/retirement, ordinary-user and
vendor preservation, then normal exit/activation/reboot and fresh admission,
public broker operation and unchanged child policy. Keep existing synthetic
replacement/reexec regression coverage distinct.

Run focused host regressions and resource-inventory review; refresh generated
coverage after registration and check links/plan. Any product/build-input edit
requires `make build` after the final edit. Mark only 004c complete; registration
and host doubles supply no native transaction acceptance.
