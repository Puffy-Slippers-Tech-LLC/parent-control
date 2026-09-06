# Test automation

Use this guide for running tests. Use the [implementation plan](TestAutomation/Test-Automation.md)
only when implementing unfinished automation. Running a test command does not
restart the implementation plan or require a model-selection ceremony.

## Daily commands

The intended interface is four commands. **These targets and their selectors
are not implemented yet**; Task 28A owns them. Current executable commands are
listed below, so planned automation is never mistaken for passing coverage.

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
| `make check-system ARTIFACT_DIR=<verified-directory>` | Existing guarded installed-system runner; detailed coverage is still being completed. |

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

Customer E2E means real keyboard/mouse operations on the installed product and
OS, real authentication and applications, real reboot/package operations, and
natural elapsed-time expiry. No mocks, hidden state writes, fake clock,
checkpoint restore, or saved-state resume may replace customer steps. Read-only
backend evidence corroborates visible behavior and other-user isolation.
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
Three-run/ten-run qualification and diagnostic reruns are explicit operations
for harness changes or flake investigation; they preserve each attempt and do
not multiply the daily suite. A real-duration wait or second package build
needed for a reproducibility assertion remains part of that test's behavior.

Removing completed setup instructions does not remove regression tests of
setup/cleanup safety, package behavior, or build reproducibility. Those can
regress when code changes. See [environment prerequisites and recovery](../tests/integration/Environment.md)
when preparing a replacement environment; do not repeat preparation on the
existing accepted baseline.

## Maintaining tests

The [test contributor guide](../tests/README.md) covers layer selection,
dependency isolation, cleanup prerequisites and requirement maintenance.
The [remaining implementation plan](TestAutomation/Test-Automation.md) contains
only work not yet accepted. Completed setup task descriptions, dated pass
counts, temporary acceptance paths and model-price comparisons are not daily
instructions.
