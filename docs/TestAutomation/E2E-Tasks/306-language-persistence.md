# 306 — Personal languages persist across accounts and offline use

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Also apply [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **180** — Public fresh/same Parent allowance setup.
- **193a** — Guarded Internet isolation and independent recovery.
- **300g** — Parent language Save/Cancel and relaunch.
- **300h** — Kiosk language Save/Cancel and re-entry.
- **300i** — Riley overlay language Save/Cancel and command relaunch.
- **300j** — Jordan/German and Riley/Hebrew station restoration and approver independence.
- **306a** — Chinese Parent presentation across child selection.

Estimate: 40–60 minutes.
Session exception: Independent administrator and child sessions, normal relaunches and one offline persistence history remain a complete customer case.

## Scope and acceptance

Compose one complete case from the [fixed recipe](../E2E-Scenario-Recipes.md#personal-language-persistence-planned-task-306).
Use Jamie/`zh-Hans`, Jordan/`de` and Riley/`he`, with English desktop languages.
Retain representative first-run/native-name/Save/Cancel observations, independent
Parent/child/approver selection, Riley overlay ↔ kiosk sharing, normal Parent and
overlay relaunch, fresh kiosk re-entry and a renewed Riley session. Run the
language changes and rereads offline with independently confirmed isolation,
then restore Internet through the shared owner. Observe German, CJK and Hebrew
public text without downloads, retained checked choices and no repeated setup.
Compare account names, request numbers, each child's policy/app rows and
independent language choices before/after. Panel refresh, dialogs/RTL rendering
and translated approval are owned by their separate recipes.

## Shared implementation

Reuse LANG01, REQUEST04, the normal Parent/overlay command entries and
`InternetIsolation`; cases supply finite values/order/assertions, not new
selectors, private preference writes or a copy of qualification workers.
For Parent's enabled 60-minute English/Chinese reads, reuse
`AccessibleUI.parent_language_state(child=..., enabled=True, language=...)`
and its registered `parent-language-{riley,jordan}-enabled-{en,zh-hans}`
operations. The `parent-language-{riley,jordan}-selected` observations prove
UID/name and closed picker without invoking the English-only settings reader.
Use each child's own immutable policy/name/balance capture. A reopened Parent
starts with Jordan in these fixtures; explicitly select Riley before a Riley
read. The [support guide](../../../tests/support/README.md#host-and-guest-boundaries)
owns these shared entry and readback details.

## Implementation entry

One planned complete case; no numeric coverage ID or executable is registered.
Allocate one stable scenario/coverage binding for the linked recipe before
implementation. Run that exact case through the maintained E2E launcher and
regenerate coverage at close-out. Prerequisite qualification is not case acceptance.
