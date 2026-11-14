# 296f — Observe allowed Lunar autostart across login

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 40–60 minutes.

Use the [supplied manual profile and autostart settings](../E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate)
in place. Report any launcher/profile setup gap before making setup changes.

Session exception: Continuous pre-login observation touches shared recorder/secret handling and requires the retained live regression set.

## Scope and prerequisites

Deliver **APP06/UI22 allowed continuous login interval**. Named consumer: task **296b** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **296d** — Lunar/tray public identity and absence/presence observations.
- **007** — LIFE02.
- **016a** — UI22.
- **004** — UI19/GDM05 distinct single-use authentication challenges.
- **052c** — TIME03.
- **180** — FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup.

## Implementation

Compose existing Lunar/tray readers with the shared login observer. Arm before child login input and preserve sealed capture, reattachment and all samples through 90 seconds after desktop readiness.

Source gap: task 016a's UI22 is `journey_blocks.observed_text` with
`UiObservations.start_trace` / `poll_trace` / `finish_trace`, qualified around one Parent
feedback edit. It is not a continuous external-app login observer.
Bind the existing recorder/boot lifecycle to public Lunar/tray samples
across login, including reacquisition before the first possible app surface and
the complete post-readiness interval. No login-observer callable or selector is
registered yet. Keep this source gap explicit; final-window absence and a
product-text trace cannot supply interval coverage. Separate normal Minecraft
launcher entry/exit/denial remains tasks 296e/296a and the complete case. No
vendor sign-in, game downloads, game launch or gameplay is required.

## Live VM acceptance

Observe working allowed autostart continuously from before login submission. Require the actual tray/Lunar result and reject blind intervals, ambiguous ownership and missing samples. Retain all applicable recorder/secret/cleanup regressions.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests system check_e2e_lunar_autostart_positive
```
