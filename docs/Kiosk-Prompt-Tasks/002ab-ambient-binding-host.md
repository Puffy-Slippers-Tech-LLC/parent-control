# 002ab — Implement safe post-layout ambient binding

Acceptance: host

Purpose: deliver the independent native source-lifetime mechanism needed before
[002a](002a-classification.md) resumes. Requires 002aa's accepted design in the
[confinement owner](../SystemDesign/Kiosk-Confinement.md#planned-post-layout-ambient-binding).
Read the [master](../Kiosk-Prompt.md#classification-prerequisite-discovery--002a),
[execution contract](../Execution-Plans.md),
[failure handling](../../tests/README.md#handling-test-failures),
[parallelism contract](../../tests/README.md#host-test-parallelism-review) and
[storage mandate](../Mandates/Test-Storage-Mandate.md).

Implement only the accepted [phase-local protocol and finite acceptance matrix](../SystemDesign/Kiosk-Confinement.md#planned-post-layout-ambient-binding) in `tools/kiosk_confinement.py`
and `tools/kiosk_confinement.h`, their necessary callers and
`tests/unit/test_kiosk_confinement.py`. Read complete layout/tree/generation/
publication and native preparation/binding/PAM functions first. Reuse
`native_mount_binding` and `preserved_password_preparation`; update the existing
resource rationale in `tools/regression_unit.py` for changed ownership/resources.
Read the applicable runtime-label and bootstrap-filesystem rules in
`tools/kiosk_confinement_policy.py`; any necessary policy/comment adjustment is
limited to the reviewed private skeleton's backing and existing caller/bootstrap
roles. The owning design specifies namespace setup before preparation, private
publication, required proof records and bounded identity-owned detach. Its five
planned selector families remain unimplemented until this task registers them.
No host filesystem mutation or installed product workflow is authorized here.

Before repair, add deterministic failing regressions at the published-layout to
native-binding boundary for an unrelated source disappearing or becoming
non-root-owned, group/world-writable or the wrong type. Register finite selector
names in the retained acceptance evidence; new selectors are unimplemented
until added. Pair each ambient case with an independent required-source control.
After repair ambient cases must admit without mounting the rejected host source;
unsafe directories are empty private directories and omitted files are absent.
Required equivalents must refuse. Check disappearance/reappearance and ownership
or type substitution at the checked descriptor boundary, not only a Python mock.

Preserve existing source/target trust, preserved identity before/after mounting,
malformed-manifest, attach, recursive read-only and staging-detach refusals.
Target or mount failures must never be treated as ambient source omissions.
Keep `test_native_binding_detaches_only_its_staging_mounts_after_readonly_clone`,
`test_native_preserved_identity_checks_every_python_assertion_field` and
`test_native_preserved_identity_refuses_real_post_measurement_file_changes` as
independent controls. Extend the private fixtures with actual published manager
and gate records reaching the native parser; verify omission/masking, unchanged
shared generation state, subsequent preparation/reuse and cleanup on every
outcome. Unknown source roles refuse. Logging failure cannot alter admission.

Required validation: affected confinement/native selectors through `tools/run-tests unit`
with exact selectors and existing explicit subprocess timeouts, including the
new failing-then-passing histories and all controls above. Retain reports and
exact source/fixture applicability. Run `make build` after final packaged edits.
Do not remove ambient layout from the digest, bypass manager matching or implement
005a–007's between-admission material/pin selection. 002a still owns its complete
original classification, alias ancestry, required completeness, metadata races
and representable publication acceptance; this prerequisite grants it no credit.
003/004/007 retain all installed obligations on their named targets.

Restore every private fixture on success/failure and finish runner-owned cleanup.
Join all workers before acceptance/cleanup. Validate changed Markdown links and
the maintained documentation consistency selection, record concise evidence in
the master/queue, close only this row, and remove this temporary brief after
migrating its references. Resume 002a with all original assertions intact.
