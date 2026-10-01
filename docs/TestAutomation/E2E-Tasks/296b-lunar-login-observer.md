# 296b — Prove the denied Lunar login interval

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 40–60 minutes.

Session exception: The complete denied login interval, same-route denial control and shared recorder/secret regressions remain required.

## Session boundary

Add the complete denied login interval and same-route explicit denial control. Reuse 296f's observer lifecycle; transient usable surfaces must fail and case 253 stays pending.

Tasks **296f** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **APP06/UI22 continuous login interval and Lunar autostart binding**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **296a** — APP01/02/03 and UI18 Minecraft local-world binding.
- **007** — LIFE02.
- **016a** — UI22.
- **004** — UI19/GDM05 distinct single-use authentication challenges.
- **052c** — TIME03.
- **180** — FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup.
- **296f** — APP06/UI22 allowed continuous login interval.

## Implementation

Compose the separately qualified Lunar/tray and Minecraft observations with
UI22 and the existing login/reboot recorder. Arm before child login submission,
preserve secret sealing, and observe tray, Lunar and game surfaces until 90 seconds
after desktop readiness. Qualify reattachment before the first possible surface;
no blind interval or final-window-only absence claim is acceptable. Reuse the
shared observer, command transport and VM lease; no new capture loop or viewer.

## Live VM acceptance

On the guarded VM, qualify working allowed autostart and a complete denied
login interval, with a real original-AppImage launch and specific public denial
as the negative control. Missing samples, ambiguous ownership and transient usable
surfaces must fail. Pass applicable recorder/secret/cleanup tests and the master's
retained regressions. This slice does not register or pass complete case 253.

Implement and register the following fixed qualification in the existing guarded
envelope before invoking it. Pass the affected cleanup/ownership regressions in
isolation first. Use the shared watch observation and intention transport.
Require independent valid entry, wrong-entry refusal, sanitized results and owned
cleanup; host tests alone do not close this row.

```sh
tools/run-tests integration check_e2e_lunar_login_observer
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
