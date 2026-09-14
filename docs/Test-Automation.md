# Test automation

Entry point for implementation and daily tests. To continue implementation:

> Continue the next unfinished task in docs/Test-Automation.md. This is the dev and host machine.

For an authorized unattended loop, run `tools/codex_slices.py start`.
[Unattended sessions](TestAutomation/Unattended-Sessions.md) covers live progress,
safe stopping, permissions and interruption recovery. The supervisor appends
reports to the [operator summary](Test-Automation-Slice-Summary.md);
implementation workers must exclude that log from reads, searches, diffs and edits.

## Continue implementation in fresh sessions

**Current scope — 2026-09-14:** prioritize customer E2E across all app surfaces,
operating and observing exactly as real users under
[E2E-Coverage.md](TestAutomation/E2E-Coverage.md). Timeout/login rejection is
only an example. Completed unit/component/system tests stay intact. Mechanical
installation, upgrade, migration and removal in Tasks 18/20 retain necessary
internal checks and follow the customer queue. The
[policy-acknowledgement design](TestAutomation/Policy-Acknowledgement.md) and
other unfinished internal matrices are separate, not automatic prerequisites.

Follow the [workflow](TestAutomation/Implementation-Workflow.md) for selection,
execution, verification and handoff. At each safe boundary reconcile
[Continuation.md](TestAutomation/Continuation.md) with the
[master checklist](TestAutomation/Test-Automation.md#unfinished-tasks), selecting
the earliest ready unchecked entry. Read only the selected
[reuse-map row](TestAutomation/Reuse-Map.md) and relevant contracts/source.

Implement one coherent slice, normally planned for 15–30 minutes. Finish owned
operations and cleanup, save next action/evidence/reassessed settings, then end
the session and reuse the prompt. Existing development/host and guarded-VM
authorization persists; a new chat does not require machine selection, old
transcripts, repeated investigations or unchanged tests.

**Quality first, weekly allowance second.** The
[model policy](TestAutomation/Implementation-Workflow.md#reassess-model-and-effort-at-every-handoff)
uses Sol high for settled implementation, Astra high for unresolved hard
boundaries, and lower settings only with adequate contracts/checks. Use Standard
processing and reassess each slice; no blanket Astra/high or max-effort pin.
Budgets trigger review, never weaker checks.

Apply the workflow's [context/output rules](TestAutomation/Implementation-Workflow.md#reduce-unnecessary-model-output):
avoid repeated context, rediscovery and scripts/transcripts. Model-written
commands cost output tokens; returned tool content costs input. Local rendering
and retained artifacts cost no additional model tokens unless sent to a model.
Preserve full diagnostic evidence.

An explicit test-run request uses the commands below; a documentation review
edits the relevant guides.

## Daily commands

For Codex execution, use the validated category commands in the
[test and diagnostic approval guide](TestAutomation/Approval-Tools.md).
`tools/run-tests --list` includes current layers and stable routes for the
planned suites. E2E executes ready declarations through its guarded controller
and refuses pending selections before VM access. Future aggregate routes still
refuse until their runners exist; approval coverage is not suite implementation.
The same guide covers read-only system diagnostics and maintenance of only the
pinned test VM, with no recurring per-file or per-operation authorization.

Prefer the approved commands that avoid recurring approval or Polkit prompts.

The intended interface is four commands. **These targets and their selectors
are not implemented yet**; deferred Task 28A retains their complete dispatch
and CI design. They are not prerequisites for the prioritized customer queue;
use the current validated selectors. The
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
| `make test-e2e` | All declared customer journeys using real actions and visible assertions; internal fault/package qualification is separately classified. | Yes |
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

After environment preparation, one `make test-all` must validate prerequisites,
capture current source (including uncommitted changes), test those host inputs,
build/verify package and fixtures, execute all required VM scenarios, collect
redacted evidence, restore the documented VM state and validate the result.
No manual inter-stage commands or source edits may mix input identities.

Local commands and CI use one inventory/dispatch, including non-pytest JS,
graphical, static, fixture/build and cleanup regressions without product
requirement IDs. Execute ordinary suites once; safety prerequisites still run
in isolation before protected operations.

Every expensive case must protect app behavior, app-owned OS integration or a
necessary harness guarantee. Use reliable supported helpers for unrelated
accounts, fixture apps and attachments; Ubuntu account-management UI/general
password behavior are not product targets. Follow
[app scope/prerequisite rules](TestAutomation/E2E-Coverage.md#scope-tests-around-the-app).

Customer E2E uses real keyboard/mouse input for asserted product operations/OS
transitions, including authentication, app use, reboot/package lifecycle and
natural expiry when under test. No mocks, hidden writes, fake clocks, checkpoint
restore or saved-state resume may replace causal steps. Declared setup is
separate. Customer acceptance uses visible behavior only; observe another user's
continued app use through their desktop. Do not collect backend product evidence
for customer assertions. Internal installation/package qualification remains
required separately under Tasks 18/20. Enumerate the complete applicable
[E2E scenario/variant matrix](TestAutomation/E2E-Coverage.md); the supplied
parent → child denial → kiosk → gameplay → expiry journey is required, not exhaustive.

Legacy runtime declarations still contain backend/fault requirements. Reconcile
the first affected scenario and only its necessary common validator adaptation;
this documentation change itself implements no runtime capability. Track completed
customer variants and frozen remaining scope in the active handoff. Scope moves
and helper passes earn no customer completion credit.

Restore only the prepared product-free baseline outside complete independent
attempts, never between steps. No new VM/overlay/snapshot. Serialize the existing
VM even across concurrent commands/`make -j`; detach writable host shares before boot.

A pass requires every expected test, scenario, variant, assertion and safe
evidence from this run under recorded source/package/environment identities.
Missing, skipped, expected-failing, stale, interrupted, flaky or failed required
results and failed cleanup prevent success. Keep original failures on diagnostic
reruns; report product, infrastructure, collection and cleanup outcomes separately.

Pin/record the release environment matrix. A separately labeled security-updates
canary checks newer dependencies without replacing release evidence or silently
changing supported environments. A pass proves defined coverage, not zero bugs.

## Keep one-time work out of daily runs

`test-*` must not perform account preparation, baseline capture/acceptance, host
tool installation, historical implementation acceptance, repeated smoke
qualification or model selection. Preparation is a prerequisite: report invalid/
missing baselines rather than silently rebuilding them.

Run each regression/required variant once per ordinary attempt. Repeated
qualification/diagnosis needs a stability question, scope, count and stop
condition under the [workflow](TestAutomation/Implementation-Workflow.md#verify-at-the-right-scope).
Preserve each attempt without multiplying the daily suite. Real-duration waits
and second builds required by reproducibility assertions remain test behavior.

Removing completed setup instructions preserves regressions for setup/cleanup,
packaging and build reproducibility. Use
[environment preparation/recovery](../tests/integration/Environment.md) for
replacement environments; do not repeat preparation of the accepted baseline.

## Maintaining tests

The [contributor guide](../tests/README.md) owns layers, isolation, cleanup
prerequisites and requirements. [Shared support](../tests/support/README.md)
routes fixtures, script imports, process capture, private buses, VM doubles and
guest assertions. Central import paths/layer classification replace imports
from collected tests and per-module path manipulation.

The [implementation plan](TestAutomation/Test-Automation.md) holds unaccepted
work. Completed setup descriptions, dated pass counts, temporary acceptance
paths and model-price comparisons are not daily instructions.
