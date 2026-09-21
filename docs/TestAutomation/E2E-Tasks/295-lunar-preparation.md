# 295 — Validate the manually prepared Lunar VM profile

Planning only; estimate 25–45 minutes excluding manual preparation. Follow the
[master](../E2E-Execution-Plan.md#execute-one-task). Required capabilities:
**006** (package operation), **036** (declared file assets). First consumer:
[E2E-052/case 253](../E2E-Scenario-Recipes.md#e2e-052).

## Scope

Deliver FIX05 under the [profile contract](../E2E-Building-Blocks.md#lunar-client-preparation-and-observation-gate).
Manual VM installation of Lunar/AppImageLauncher and preparation of Minecraft's
test account, assets and local world is allowed before the attempt. Bind pinned
versions/digests, the original space-containing AppImage path, integrated
launcher, enabled child autostart/tray settings and private credential references.
No product policy/grant setup and no host installation are part of this task.

Establish repeatable availability after the existing runner restore using its
maintained preparation/provisioning path. Do not invent another snapshot,
overwrite the baseline, skip restore or add an automatic installer to FIX05.
Keep FIX04's transfer-only boundary. Missing assets, expired sign-in, mandatory
updates or unresolved restored-state ownership leave this task blocked.

## Qualification and close-out

Implement one read-only fixture-validation operation in the existing envelope.
Use the guarded VM/watchvm path to verify an independently prepared valid profile
after normal restore and refusal of missing, drifted or wrong-account inputs.
Supporting setup checks are engineering evidence, not a blocked-launch pass.
Run affected host safety/unit checks first; keep public app/secret observations
for task 296. Implement a bounded qualification route before invoking it.

Follow [close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup) only
after real qualification and cleanup. Record the actual callable/scope in FIX05,
keep case 253 pending, and select the next eligible queue task. No VM work has
been performed by this planning task.
