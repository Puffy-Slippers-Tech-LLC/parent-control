# F32 — Own fixture processes and probe descendants

Acceptance: host
Requires: F31

## Scope and implementation

Implement the process half of the
[quiescence protocol](../Fixture-Design.md#fixture-only-native-acknowledgement-protocol).
Read the C GUI owner/Python child, owned command/process and systemd lifecycle
helpers, exact cleanup contracts and their tests. Retain the native supervisor,
cgroup, boot, PID/start and pinned handles before admitting fixture/probe input.
Build the fixed native probe through the shared target builder as an engineering
member of native-runtime with its exact source/toolchain/content identity; transfer
it only for the protocol's transient closure. Do not add another cache profile,
compile in the guest or borrow a host binary with an unverified target label.
The fixed probe supports only finite open/exec witness operations, private nonce
executable identity and selected UID. Drop credentials before descriptor-based
exec; keep the unique executable identity through the observed syscall.
Support the design's selected-UID descriptor reopen/exec witnesses against
privately staged added/replacement bytes. Preserve pinned object identity and
exclude unrecorded access/writers; a permission failure before native evaluation
cannot supply a barrier denial. Target event/hash semantics remain F05/F06 proof.

Close new host fixture actions before inspection. Explicit quiescence stops only
recorded fixture owners and proven descendants, observes actual exit and rechecks
inherited mappings/descriptors and the entire old closure under the barrier.
Unknown processes or an interpreter whose relationship cannot be established
refuse live mutation. Do not infer ownership from argv, parent PID or unit name.
Use startup/runtime/stop deadlines and identity-bound ambiguous-create recovery.
An unavailable supervisor capability refuses rather than using a name scanner.

## Finite validation and cleanup

Use private process/cgroup/systemd doubles and bounded waited children for the
C/Python pair, fork/reparent/escape, open-FD inheritance, PID reuse, parent crash,
cancellation and lost start/stop replies. Prove retained handles and nonce
executables cannot be reused or retired while any descendant still references
them. Preserve unknown/product processes. Run exact ownership/cleanup safety
selectors and all applicable resource classifications. No live VM, systemd
service or host native policy is changed. This has a 30–60 minute exception for
one indivisible supervisor/descendant recovery state machine. Update support
owners and close through the [master](../Fixture-Execution-Plan.md).
