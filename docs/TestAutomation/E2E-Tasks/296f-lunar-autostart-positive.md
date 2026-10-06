# 296f — Observe allowed Lunar autostart across login

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 40–60 minutes.

Session exception: Continuous pre-login observation touches shared recorder/secret handling and requires the retained live regression set.

## Scope and prerequisites

Deliver **APP06/UI22 allowed continuous login interval**. Named consumer: task **296b** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **296a** — APP01/02/03 and UI18 Minecraft local-world binding.
- **007** — LIFE02.
- **016a** — UI22.
- **004** — UI19/GDM05 distinct single-use authentication challenges.
- **052c** — TIME03.
- **180** — FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup.

## Implementation

Compose existing Lunar/tray/game readers with the shared login observer. Arm before child login input and preserve sealed capture, reattachment and all samples through 90 seconds after desktop readiness.

## Live VM acceptance

Observe working allowed autostart continuously from before login submission. Require the actual tray/Lunar result and reject blind intervals, ambiguous ownership and missing samples. Retain all applicable recorder/secret/cleanup regressions.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_lunar_autostart_positive
```
