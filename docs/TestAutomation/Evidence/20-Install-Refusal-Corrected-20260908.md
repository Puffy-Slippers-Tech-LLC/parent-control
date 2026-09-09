# Task 20 deliberate installation refusal — corrected live qualification

Scope: fixed helper qualification, not E2E-002 acceptance. Task 20 remains the
earliest ready unchecked task and the all-task guarded VM clearance persists.
Actual settings: `gpt-5.6-sol` / `high`, Standard processing.

## Inputs and verification

`tools/run-tests artifacts build` produced and verified
`/tmp/onpc-test-artifacts-n07g3pi2` from revision
`b47f87faa3dfa4df6789033e34f7253bb891397e`. Source SHA256:
`d2445afe08ce142e7fa0176968083022f59e4638d287c277d02a7bdaf0352295`.
Package SHA256:
`760cb8bdbf03d9b68a273e171df502bb6e0b82e55ab4f6f2aaf39961388149b7`.
The isolated cleanup/ownership selection passed **526 tests plus 3 subtests**
in 5.21 seconds. The installed dispatcher repeated that closure successfully.

The guarded deliberate-refusal selection exited **0** after **1,227.72
seconds**. This is the thirteenth installation-authentication attempt overall:
the successful installation and corrected refusal qualifications passed; the
eleven historical failures remain failed. No second attempt was started.

## Qualified result

The run verified current source and artifact provenance, all 92 transferred
entries, fixture credentials, usable GDM interaction, real serial login, product
absence, audited sudo-rs 0.2.13-0ubuntu1, exact prompt/recipient/process
continuity and disabled password-character echo. It submitted the fixed invalid
value once, observed the first rejection and submitted no retry password. The
corrected serial interrupt returned to the proved fixture shell. Independent
postconditions established no live installer child, product package, core
payload or product reboot marker and unchanged boot identity. Serial logout and
GDM return then passed.

| Evidence | Location |
| --- | --- |
| Terminal result, provenance, ordered stages and split outcomes | `/tmp/onpc-graphical-smoke-cm06m6zu/result.json` |
| Ordered public controller evidence | `/tmp/onpc-e2e-evidence-ucyawwes` |
| Worker result and resource closure | `/tmp/onpc-e2e-evidence-pqiaucy5/worker-result.json` |
| Fresh artifact manifest | `/tmp/onpc-test-artifacts-n07g3pi2/artifact-manifest.json` |

Product remained `not-run`, as required for this helper qualification. The red
successful-install notice, actual customer reboot, installed layout/readiness
and the two startup-fault variants remain outside this result. The historical
intermittent executable refusal did not recur and remains open for later live
attempts; it does not invalidate this passed fixed refusal path.

## Cleanup and next action

Worker `worker-7b36224fe629469e93d7730414fd38a5` stopped; callback and display
closed; normal shutdown passed. The outer guard restored and verified the
retained baseline, preserved host/source inputs and released the lease. Final
pinned-VM state is off. Infrastructure, collection and cleanup all passed; all
commands exited and no recovery or exported screenshot remains. No approval,
execution-policy or Polkit denial occurred.

Next, extend the accepted authenticated-install boundary into the clean
E2E-002 journey: retain private output while asserting the final red reboot
notice, perform the customer-visible reboot, reconnect on a changed boot and
correlate usable GDM with fapolicyd and broker readiness. Add local refusal and
cleanup coverage before one guarded attempt with fresh artifacts. Keep the two
E2E-028 startup failures separate.
