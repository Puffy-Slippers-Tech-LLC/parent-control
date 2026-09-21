# 296 — Qualify Lunar tray, game and login observations

Planning only; estimate 40–60 minutes. Follow the
[master](../E2E-Execution-Plan.md#execute-one-task). Required capabilities:
**295** (prepared profile), **007** (customer reboot), **079a** (native public
launch/denial), **052c** (bounded real waits). First consumer:
[E2E-052/case 253](../E2E-Scenario-Recipes.md#e2e-052).

## Scope

Deliver APP06 and the Lunar/Minecraft bindings of APP01/02/03, UI18 and UI22's
login-interval observer under the [profile and observation contract](../E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate).
Resolve real external providers through the repository's approved exception;
do not invent IDs or reuse unqualified generic title/coordinate selectors.
Distinguish tray close from genuine Quit. Bind a Minecraft local-world action
with an independently observable result, not merely a launcher menu.

Reuse the shared recorder/observer across child login: arm before submission,
preserve secret sealing, and observe public tray/Lunar/game surfaces through the
full 90-second interval. Missing samples or unresolved surface ownership refuse;
final absence cannot mask a transient successful launch. No hidden process,
fapolicyd-rule or service checks may supply customer results.

## Qualification and close-out

On the guarded live VM, qualify allowed autostart, tray restore, original-AppImage
command launch, playable Minecraft, ordinary exit/Quit and complete absence with
the recognized surrounding desktop. Exercise wrong-owner, ambiguous, incomplete
and unavailable-provider refusal without input replay. Use independently valid
entry states and the existing worker/observation path. Split this task before
implementation if separate providers require substantial independent work.

Run affected safety/adapter tests before VM integration. Login/recorder changes
also require the master's retained live regressions. Implement a bounded slice
qualification route before invoking it; a diagnostic slice cannot pass case 253.
After qualification/cleanup, follow the
[close-out contract](../E2E-Execution-Plan.md#completion-and-document-cleanup),
record actual callable/qualified scope, and leave the complete scenario pending.
