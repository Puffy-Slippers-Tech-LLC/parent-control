# Test automation

This is the entry point for continuing implementation and for running tests.
For the remaining implementation, repeat this exact prompt in each new session:

> Continue the next unfinished task in docs/Test-Automation.md. This is the dev and host machine.

To automate that loop until the checklist is complete, run
`tools/codex_slices.py start`. Each slice gets a fresh Codex session.
See [unattended sessions](TestAutomation/Unattended-Sessions.md) for progress,
safe stopping, permissions and interruption recovery. The launcher displays
session output live and appends only end-of-session reports to
[the slice summary log](Test-Automation-Slice-Summary.md). That log is for the
operator; implementation sessions must not read or edit its accumulated history.

## Continue implementation in fresh sessions

1. Select the earliest ready unchecked task in the
   [master checklist's order](TestAutomation/Test-Automation.md#unfinished-tasks),
   reconciling [Continuation.md](TestAutomation/Continuation.md) with that order.
   The [workflow](TestAutomation/Implementation-Workflow.md#start-with-one-bounded-result)
   owns task selection, blocker rechecks, execution, verification and handoff rules.
2. Implement and verify one coherent slice, normally planned for 15–30 minutes.
   Finish the current operation and safe cleanup before handing off. The agent
   saves the next action, reusable evidence and reassessed settings, then tells
   you that you can end the session. Start a new session with the same prompt.

**Quality takes absolute precedence; conserving weekly usage allowance is the
secondary objective.** Follow the
[model policy](TestAutomation/Implementation-Workflow.md#reassess-model-and-effort-at-every-handoff):
Sol high for settled implementation, Astra high for unresolved hard boundaries,
and lower settings only with adequate contracts and checks. Use Standard
processing and reassess each slice; no blanket Astra/high or max-effort default.
Reduce repeated context and rediscovery. Budgets trigger review, never weaker checks.
The [reuse map](TestAutomation/Reuse-Map.md) identifies opportunities across all
remaining tasks; consult only the relevant row during implementation.

Apply the [output rules](TestAutomation/Implementation-Workflow.md#reduce-unnecessary-model-output)
to avoid repeated scripts, command transcripts and irrelevant tool reads.
Model-written commands use output tokens; tool results sent back to the model
use input tokens. Local terminal rendering and retained artifacts add no model
tokens unless their contents are sent to a model. Keep full diagnostic evidence.

The prompt establishes development/host scope and the existing guarded test VM.
Preserve that authorization and the compact handoff across sessions; no machine
selection, old transcript, completed investigation or repeated test is needed
merely because the chat is new.

An explicit request to run tests uses the commands below. A documentation
review edits the relevant guides.

## Daily commands

For Codex execution, use the validated category commands in the
[test and diagnostic approval guide](TestAutomation/Approval-Tools.md).
`tools/run-tests --list` includes current layers and stable routes for the
planned suites. E2E executes ready declarations through its guarded controller
and refuses pending selections before VM access. Future aggregate routes still
refuse until their runners exist; approval coverage is not suite implementation.
The same guide covers read-only system diagnostics and maintenance of only the
pinned test VM, with no recurring per-file or per-operation authorization.

[IMPORTANT] **Try your best to use commands that does not need user approve or show PoliKit prompt.**

The intended interface is four commands. **These targets and their selectors
are not implemented yet**; Task 28A owns their complete dispatch and CI. The
smaller [F1 task](TestAutomation/Task-F1.md) brings guarded installed selectors
and diagnostic timing forward into `check-system`. F1 is complete: its
host-safe `LIST=1` inventory, guarded case forwarding, stage timing, split
diagnostic outcomes, and selected-input provenance are implemented and qualified
in the VM. Installed product coverage remains under development. Use the current
commands below for runs.

| Command | Default scope | Test VM |
| --- | --- | --- |
| `make test-fast` | Static checks, unit/property/contracts, private-D-Bus components, GTK, child JavaScript/GJS and nested-Shell tests, plus local coverage evidence. | No |
| `make test-system` | All installed-package and OS integration tests: identity, authorization, enforcement, time, activation, migration, removal, reinstall, and runner guards. | Yes |
| `make test-e2e` | All required graphical customer journeys and declared graphical fault/recovery cases. | Yes |
| `make test-all` | All required suites and supported environments, build reproducibility, and final execution/evidence/requirement validation. | Yes |

`test-fast` combines unit and component work. Full GTK/nested-Shell coverage may
take minutes; use focused selections for quicker feedback, without silently
dropping cases from the default suite.

Planned selectors:

```sh
make test-fast COMPONENT=child
make test-fast TYPE=unit
make test-system AREA=package
make test-e2e SCENARIO=E2E-023
make test-all LIST=1
```

`LIST=1` lists the selected scope, prerequisites, VM use, categories, and
available selectors without running tests or starting a VM. A scenario family
includes every required variant; explicitly selecting a variant yields a
partial result. Unknown or unexpectedly empty selections fail. `test-all`
rejects selectors that narrow coverage. Shared request-form selections include
both kiosk and child-overlay modes and all applicable safety prerequisites.

## Commands available now

The [Makefile](../Makefile) is the executable source of truth until the four
commands are delivered. The component and static suites are **not** fully
included in today's `make check`.

| Current command | Actual scope |
| --- | --- |
| `make check` | Unit/contracts, private-D-Bus components, C/JS/Python/XML syntax and source guards, stage-mode requirement validation. |
| `make check-component` | Private-D-Bus, Node/GJS, GTK, and nested-Shell components. |
| `make check-static` | ShellCheck and GJS static/module checks. |
| `make check-unit` | Unit and contract modules, including property tests. |
| `make check-system LIST=1 [AREA=<area> [TEST=<case-id>]]` | Host-safe installed-case inventory and prerequisite resolution; no artifacts, root, or VM use. |
| `make check-system ARTIFACT_DIR=<verified-directory>` | Existing guarded installed-system runner; detailed coverage is still being completed. |
| `make check-system ARTIFACT_DIR=<verified-directory> AREA=<area> [TEST=<case-id>]` | Guarded partial installed run for registered `package` or `authorization` scope, including required package/reboot phases. |
| `make check-e2e LIST=1 [SCENARIO=<family-or-variant>]` | Host-safe inventory through the validated E2E launcher; E2E-001 is runnable; the other 156 variants remain pending. |
| `make check-e2e ARTIFACT_DIR=<verified-directory> [SCENARIO=<family-or-variant>]` | Ready Python callbacks dispatch through the accepted guarded controller. E2E-001 combines qualified GDM/serial-return evidence with the accepted controller. Pending selections refuse before privilege or VM access. |

Selected runs record their exact expected and executed JUnit identities and
reject missing, additional, duplicate, failed, or skipped cases. They are
partial diagnostic results and cannot satisfy full-suite acceptance. Guest
pytest arguments remain unsupported.
During implementation, full command lists in task documents are acceptance checks;
use [focused verification](TestAutomation/Implementation-Workflow.md#verify-at-the-right-scope)
for edits and do not rerun unaffected suites merely to resume a chat.

Before a current host-integrated command that terminates processes, run its
[cleanup-safety prerequisites](../tests/README.md#cleanup-safety-prerequisites)
in isolation. Non-VM UI pytest must use `tools/run-ui-tests --timeout <duration>
<pytest arguments>` directly. Never route a UI or guest suite through a generic
pytest marker command that bypasses its launcher or guards.

The [installed runner guide](../tests/integration/README.md) documents artifact
building, privileges, evidence and recovery. Do not supply a remembered
acceptance-run directory: verify the current source/package inputs. There is
currently no implemented comprehensive graphical E2E or `test-all` pass.

## What a complete run must establish

After the documented environment is prepared, one `make test-all` invocation
must validate prerequisites, capture current source inputs including
uncommitted changes, run host tests against those inputs, build/verify the
package and fixtures, run all required VM scenarios, collect redacted evidence,
restore the documented VM state, and validate the complete result. No manual
commands are required between stages. Source edits during a run cannot mix
host results and VM artifacts from different inputs.

Use one suite inventory and runner dispatch for local commands and CI. Include
non-pytest JavaScript, graphical, static, fixture/build, and cleanup-safety
checks even when they have no product requirement ID. Avoid duplicate ordinary
suite execution; safety prerequisites still run in isolation before the
operations they protect.

Every expensive test must protect an app behavior, an app-owned OS integration,
or a necessary harness safety guarantee. Use the cheapest reliable supported
helper to establish unrelated prerequisites, such as real user accounts,
fixture applications and attachment files. Ubuntu's account-management UI and
general password behavior are not product acceptance targets. Follow the
[scope and prerequisite rules](TestAutomation/E2E-Coverage.md#scope-tests-around-the-app).

Customer E2E uses real keyboard/mouse input for the product operations and OS
transitions the journey asserts, including real authentication, application use,
reboot/package lifecycle and natural expiry where those are under test. Required
causal steps cannot be replaced by mocks, hidden state writes, fake clocks,
checkpoint restore or saved-state resume. Declared prerequisite setup is separate
from those steps. Read-only backend evidence corroborates visible behavior and
other-user isolation.
Follow the [E2E operations and coverage contract](TestAutomation/E2E-Coverage.md)
and enumerate the complete applicable scenario/variant matrix. The supplied
parent → child denial → kiosk → gameplay → expiry example is one required
journey, not the coverage limit.

Only the already-prepared product-free baseline may be restored outside
complete independent attempts. Never create a new VM/overlay/snapshot or
restore between steps. Serialize the existing VM even under concurrent commands
or `make -j`; detach writable host shares before test boots.

Success requires all expected tests, scenarios, variants, assertions and
evidence from this run, for the recorded source/package/environment identities.
Missing, skipped, expected-failing, stale, interrupted, flaky or failed required
results prevent success, as do unsafe/missing evidence and cleanup failure.
Preserve the original failure on a diagnostic rerun. Report product,
infrastructure, collection and cleanup outcomes separately.

The release environment matrix is pinned and recorded. A separately labeled
security-updates canary checks newer dependencies; it cannot silently change
the supported matrix or replace release evidence. A pass establishes the
defined regression coverage, not the absence of every possible bug.

## Keep one-time work out of daily runs

Account preparation, baseline capture/acceptance, host tool installation, historical
implementation acceptance, repeated smoke qualification, and model selection
are not test suites and must not run from `test-*`. The prepared machine is a
prerequisite; an invalid/missing baseline is reported, never rebuilt silently.

Run each registered regression and required variant once per ordinary attempt.
Repeated qualification and diagnostic reruns need a stated stability question,
selected scope, count and stop condition under the
[implementation workflow](TestAutomation/Implementation-Workflow.md#verify-at-the-right-scope).
They preserve each attempt and do not multiply the daily suite. A real-duration
wait or second package build
needed for a reproducibility assertion remains part of that test's behavior.

Removing completed setup instructions does not remove regression tests of
setup/cleanup safety, package behavior, or build reproducibility. Those can
regress when code changes. See [environment prerequisites and recovery](../tests/integration/Environment.md)
when preparing a replacement environment; do not repeat preparation on the
existing accepted baseline.

## Maintaining tests

The [test contributor guide](../tests/README.md) covers layer selection,
dependency isolation, cleanup prerequisites and requirement maintenance.
The [shared support guide](../tests/support/README.md) routes reusable fixtures,
script imports, process capture, private buses, VM doubles and guest assertions.
Pytest import paths and layer classification are maintained centrally; tests
must not import collected cases or repeat module-level path manipulation.
The [remaining implementation plan](TestAutomation/Test-Automation.md) contains
only work not yet accepted. Completed setup task descriptions, dated pass
counts, temporary acceptance paths and model-price comparisons are not daily
instructions.
