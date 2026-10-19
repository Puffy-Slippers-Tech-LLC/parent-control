# 002a — Finish ambient classification and required-input controls

Acceptance: host

Read the [master](../Kiosk-Prompt.md), completed failure map, directory trust/
layout/tree/publication functions and their native binder. Review the existing
candidate and reuse its private fixtures under the parallelism contract.

Finish the finite classification branches for non-root/group/world-writable
directories, files, links, special types, separators, non-UTF-8 names and
unavailable metadata. Mask/omit irrelevant entries without reading contents or
changing the host. Check representability through binding publication, not only
the returned layout. Preserve required native/privileged files, reserved roots,
lexical alias ancestors and intermediate target chains; late owner/type/mode
drift, missing inputs and required metadata errors must refuse.

Add independent required-versus-ambient controls and deterministic disappearance/
readlink races. Reproduce the reviewed alias-parent omissions and non-UTF-8
publication failure before fixing them. Verify manager/gate publication contains
no omitted/masked host source; logging failure cannot change admission.

The independent host reproduction is retained at
`output/test-runs/host/exports/onpc-artifact-export-tmc1qzhs/report.md`
(run `20261019T061016Z-d39f14ad`).
Its three post-inventory alias/target ownership controls did not raise; the
non-UTF-8 filename raised `UnicodeEncodeError` at binding publication. Reproduce
these before repair and retain permanent regressions at the actual trust/layout
and publication boundaries; the removed review probes supply no maintained pass.

The follow-up review retained five failing host probes in
[the exported report](../../output/test-runs/host/exports/onpc-artifact-export-3obq7d2l/report.md)
(run `20261019T061847Z-d1c50a84`). In addition to manager/gate non-UTF-8
publication and ambient-generation failures, preparation accepted an inventory
record whose required destination was absent from the layout while its measured
substitution source remained available. The current completeness check covers
only preserved executables. Require every measured native destination and required
alias chain to reach its intended private binding or refuse before publication;
cover transient disappearance/reappearance and required link/type changes. This
probe models the post-inventory boundary, not an installed filesystem race.

Also cover ambient drift after layout and before native binding. The existing
native `unowned-directory`/writable-input controls correctly refuse an unsafe
bind, but the unchanged binder aborts the whole entry when a previously trusted
unrelated source disappears or becomes untrusted. Safe classification/pinning or
bounded retry must preserve those native refusals while preventing an ambient
source from becoming an entry prerequisite. Reuse the native fixture and record
this distinction; do not weaken its required-input assertions. If this requires
an independent mechanism beyond this slice, insert a finite prerequisite under
the master before implementation rather than absorb it here.

Run affected confinement/native host selectors through the maintained launcher,
update applicable resource rationale and build after final packaged edits.
Restore private fixtures on every outcome and retain original failures and exact
results. This row grants no native installed acceptance or diagnostic-export pass.
