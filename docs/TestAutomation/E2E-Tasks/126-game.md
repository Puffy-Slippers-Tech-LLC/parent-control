# 126 — Compose windowed gameplay through natural expiry

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP05/FLOW10 windowed game**. First scheduled consumer: [E2E-023, case 126](../E2E-Scenario-Recipes.md#e2e-023).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **126a** — Game APP01/02/03/04 and FLOW08 usable activity.
- **062** — TIME04.
- **065a** — FLOW13 grant-only profile and explicit revoke preparation.

## Implementation

Reuse the qualified real-game launch, usability and activity callables. Prepare its declared windowed mode/level through shared supported launch options or keyboard shortcuts, then compose APP05's independent mode/level observation and APP03 gameplay input/effect. Bind any startup options before FLOW08 launches; never relaunch retained activity for preparation. Compose FLOW10 from game FLOW08, APP05, APP04 and TIME04. Preserve real gameplay and bounded public results; no settings-menu tour, fake game, timer or private state probe.

Grant-only time is sufficient for this natural-expiry qualification. Reuse
126a's fixed game action and public progress; the combined time-profile
qualification is not an input to this slice. `gui_application.py::main` currently
offers a move action and public score but no mode/level operation; 126a/APP05
must bind the one declared starting level and independently observable windowed
mode before composing TIME04. Reuse unchanged launch/activity evidence and
qualify only the new mode/expiry composition.

## Live VM acceptance

On the VM actually play the declared real windowed level, observe input effects and a recognizable activity, then play a short grant to natural lock. Missing public locators remain a named prerequisite.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_game
```
