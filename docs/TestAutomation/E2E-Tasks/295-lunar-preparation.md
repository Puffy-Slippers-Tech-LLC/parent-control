# 295 — Validate the manually prepared Lunar VM profile

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **006** — LIFE04 install only.

First consumer:
[E2E-052/case 253](../E2E-Scenario-Recipes.md#e2e-052).

## Scope

Deliver FIX05 under the [profile contract](../E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate).
Manual VM installation of Lunar/AppImageLauncher and preparation of Minecraft's
test account, assets and local world is allowed before the attempt. Bind pinned
versions/digests, the original space-containing AppImage path, integrated
launcher, enabled child autostart/tray settings and private credential references.
No product policy/grant setup and no host installation are part of this task.

Establish repeatable availability after the existing runner restore through
the authorized `tools/prepare-vm` route and its finite owned inventory,
under the [baseline mandate](../../Mandates/VM-Mandate.MD#vm-host-setup-and-baseline).
Do not create alternate snapshots, overwrite baseline state outside that route,
skip restore or add an automatic installer to FIX05.
Read the restored real-app inputs in place; the FILE05 copy/rename and FIX04
synthetic-file qualification are not prerequisites for this read-only verifier.
Missing assets, expired sign-in, mandatory
updates or unresolved restored-state ownership leave this task blocked.

## Qualification and close-out

Implement one read-only fixture-validation operation in the existing envelope.
Use the guarded VM/watch path to verify an independently prepared valid profile
after normal restore and refusal of missing, drifted or wrong-account inputs.
Supporting setup checks are engineering evidence, not a blocked-launch pass.
Run affected host safety/unit checks first; keep public app/secret observations
for tasks 296, 296a and 296b. Implement and register the planned fixed qualification in
the existing guarded envelope before invocation:

```sh
tools/run-tests integration check_e2e_lunar_profile
```

Follow [close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup) only
after real qualification and cleanup. Record the actual callable/scope in FIX05,
keep case 253 pending, and advance to the following unchecked queue row. This brief does not claim that manual preparation or VM qualification has occurred.
