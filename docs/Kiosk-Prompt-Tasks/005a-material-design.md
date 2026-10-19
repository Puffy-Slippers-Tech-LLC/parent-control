# 005a — Design material identity and immutable pins

Acceptance: review

Read the [master](../Kiosk-Prompt.md), completed native audit, complete prepare,
generation verification/publication, binding/staging-detach functions and
canonical native-update witnesses.

Define the finite required-material versus ambient-layout transition table:
config/policy, required native/library bytes, privileged metadata, actually
consumed runtime roots, ambient add/remove/mode/owner/kind changes and source
disappearance/replacement. Required drift stays closed; ambient software cannot
become a new admission prerequisite.
Independent host evidence at
`output/test-runs/host/exports/onpc-artifact-export-tmc1qzhs/report.md`
(run `20261019T061016Z-d39f14ad`) shows an
unrelated empty-directory addition changing the digest and raising
`manager-generation-stale` after an unchanged layout had admitted. Preserve this
before/after control through 006b and real installed 007 acceptance; it is not
proof about an installed manager or the eventual immutable-pin design.
Keep the existing declared required-input scope. Add a runtime input only when
the changed retained-view route demonstrably consumes it and the safety contract
requires it; this task does not inventory or qualify all installed software.

Specify immutable pin storage, exact source allowlists, ownership, identity and
lifetime after native staging mounts detach. Removing layout from a digest or
reconstructing from vanished host siblings is insufficient. Cover interruption,
foreign/replaced state and bounded recovery without killing unowned managers.

Keep enduring design in confinement/lifecycle owners. Acceptance is a reviewed
material/pin design with independent positive/negative witnesses for 006a/006b.
005 reviews its manager/concurrency/native admission composition. Validate links
and close only this design slice; no host or installed pass is supplied.
