# Established regression command — 2026-09-11

Implemented `make test-all`, equivalent to `tools/run-tests all`, for the
user-requested established regression scope. Pending roadmap scenarios remain
excluded. No roadmap task was advanced.

## Command behavior

The [runner](../../../tools/regression.py) discovers current pytest cases,
the full installed-system selection, and ready E2E variants through the existing
launchers and inventory. Non-pytest suites and build steps count as command
checks. The terminal shows colored category counts and overall progress only.
Generated reports are private, uniquely named, and ignored by Git so live
updates cannot invalidate package provenance. Each received output chunk is
flushed and fsynced before progress processing; failures are emitted through
pytest hooks when reported. Detailed guest failures remain in private guest
evidence, with registered failure events immediately forwarded to the report.

Unattended execution uses the existing noninteractive authorization check and
default-deny Polkit policy. Cancellation propagates through owned stdin pipes;
controllers signal only their directly spawned pidfds and wait for cleanup.
The maintained helper and Make approval rule were installed through
`./setup.sh --test-tools-only`. An existing Codex session needs a restart to
load the new Make rule; its already-approved `tools/run-tests all` route works.
See [command usage and scope](../../../tests/README.md#all-established-regressions).

## Verification

- Focused launcher boundaries: 246 passed.
- Focused regression/system checks: 246 passed.
- Final dedicated reporting/cancellation checks: 15 passed, covering immediate
  failure persistence, interruption, output-sink failure, owned cleanup,
  unrelated-process preservation, skip refusal and automatic ready-case discovery.
- `make check`: 7,425 unit/contract and 58 component tests passed before the last
  focused test additions. The full aggregate below includes those additions.
- A real Ctrl+C probe exited 130 after cleanup and retained its partial report:
  `test-all-runs/20260911T184229Z-1c2ea8a9/report.md`.
- Documentation links and `git diff --check` passed.

The full `tools/run-tests all` invocation finished with **exit status 1**.
It was not retried or converted to a pass. Its live report is
`test-all-runs/20260911T184429Z-c6f18811/report.md`, with final category state in
the adjacent `progress.json`.

| Category | Result |
| --- | --- |
| Isolated cleanup prerequisites | 713 passed; 3 subtests passed |
| Unit and contracts | 7,430 passed; 115 subtests passed |
| Private D-Bus components | 58 passed |
| UI and nested Shell | 140 passed in 951.57 seconds |
| Fixture runtime | Passed |
| Source/traceability, static, Node, GJS, backend | All passed |
| Two package builds and reproducibility | Passed |
| Installed-system suite | All 240 executions passed; product, infrastructure, collection and cleanup outcomes passed |
| E2E-001/gdm-observation | Infrastructure failure during shutdown after all nine observations completed |

The dashboard finished at 8,592/8,592 checks, with the E2E row and overall
result red. Completion percentage does not imply success.

## Retained E2E failure

Ready, GDM, selected account, dismissed prompt, serial password, authenticated
session, command, logout and GDM-return observations all completed. The later
callback reported `Requested operation is not valid: domain is not running`.
The worker recorded `worker-execution-failed`; its lifecycle lacked completed
poweroff/status-off receipts and `shutdown_verified` remained false. The
exact failing libvirt API is not identified in the retained exception record;
a shutdown race is a hypothesis, not an established cause.

Worker and callback resources closed. Outer VM restoration reached lease phase
`complete`, and a final `tools/test-vm status` independently confirmed the pinned
VM was off (`state=5`, `id=-1`). Scenario cleanup/evidence outcomes remain failed
because normal worker shutdown and acceptance evidence were incomplete. No
change was made to the E2E lifecycle code to suppress this failure.

- Worker result: `/tmp/onpc-e2e-evidence-xns4fdan/worker-result.json`.
- Invocation evidence: `/tmp/onpc-e2e-evidence-2z5olrfc/`.
- Scenario evidence: `/tmp/onpc-e2e-evidence-dm1z48sm/`.
- Raw graphical evidence: `/tmp/onpc-graphical-smoke-ovdn0d05/`.
- Passing system result: `/tmp/onpc-system-g4iezjxi/evidence/result.json`.
- Reproducible artifacts: `/tmp/onpc-test-artifacts-mnaxh3ck` and
  `/tmp/onpc-test-artifacts-rl3j735h`.
- Tested source digest: `268c29fe6d78eada5fa664c967477c1fe3db86e2dd16bf9b52444e8da64284aa`.
- Package digest: `5fefd77d2fe1a1c40461fbb13229656cd3ab6b66934d6c42c99e7f7b4d8fea2c`.

This summary was written after execution. All launched commands have finished;
no worker or test session remains active. Original diagnostics were preserved.
