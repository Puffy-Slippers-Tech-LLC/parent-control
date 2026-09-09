# Task 20 installed-layout observation — 2026-09-09

## Result

E2E-002 now has a fixed, read-only post-reboot observation for the installed
package layout. The guest program consumes the package-derived
`installed-files.json` already transferred by `AssetTransfer`; it checks each
regular file or symlink, root ownership, the restricted Parent desktop group,
exact modes/targets, `dpkg --verify`, private configuration permissions, PAM
hooks, both Polkit action registrations, the session Polkit rule, and both
session descriptors. It returns only a count, inventory digest, and success
flag. `InstallationBoundary` compares that digest with the controller-held
`VerifiedInputs.asset_files` identity and latches every probe, provenance,
phase, or mismatch failure.

The graphical callback runs this observation after the customer reboot, GDM
return, and both startup observers, with a final unchanged-boot check before it
publishes the acknowledgement. This is locally tested and not live-qualified.
It does not establish graphical notice visibility, final artifact preservation,
or Task 20 acceptance.

## Verification and cleanup

The focused unit selection covering the exact guest program, transport output
grammar, installation boundary, and graphical controller passed 1,446 tests.
It includes malformed/tampered inventories, missing or incorrect files,
ownership/group/mode/symlink failures, package verification, PAM/Polkit faults,
unsafe output, digest mismatch, phase/provenance failure, interruption, latching,
and successful callback composition. Link validation found no missing targets,
and the final boundary/controller adjustment passed its 91-test focused rerun;
final `git diff --check` passed. Two `make check` attempts, including the
approved outside-sandbox retry, each passed 5,746 of 5,747 tests and failed
`ExtensionManagerTests.test_global_extension_switch_fails_before_activation_writes`:
concurrent unrelated extension-manager edits changed the global-switch behavior
without updating that test, and its offline subprocess also received `EPERM`.
This slice did not alter or retry that other work through another route. No VM
lease, guest process, screenshot export, or background command was created; all
commands exited.
