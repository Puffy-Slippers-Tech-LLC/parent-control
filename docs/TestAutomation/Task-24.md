# Task 24 — Kiosk customer journeys

Follow [E2E-Coverage.md](E2E-Coverage.md). Enter the real kiosk from GDM, operate
the installed request form and observe the return to GDM. Reuse shared form and
secret-safe input helpers. No fake agent, direct approval or backend assertions.

## Implementation slices

Complete kiosk entry/request/exit before expanding the form cases. A minimal
kiosk helper may be completed by Task 22 or another first consumer; acceptance
of all Task 23 cases is not a prerequisite.

## Task 24A

- Title: Kiosk entry and request-only interaction.
- Depends on: accepted graphical runner, installed package and account fixtures.
- Default settings: `gpt-5.6-sol` / `high`.
- Customer scope: E2E-016.
- Work:
  1. Select the kiosk at GDM and observe the fullscreen request surface.
  2. Try normal available navigation and shortcuts for desktop, Parent, terminal,
     settings and other app access. Observe that the session remains request-only.
     Do not inspect service lists, policies or containment internals.
  3. Complete/cancel a real request and observe the same restriction and normal
     exit. Keep password entry in the real authentication prompt.
- Verification/completion: the finite entry/restriction/exit variants pass through
  customer actions with visible evidence and existing safeguards.
- Separate work: agent-stop/restart qualification and
  `E2E-028/kiosk-auth-agent` are outside customer E2E. Existing tests remain;
  do not add that internal intervention to this task.

## Task 24B

- Title: Kiosk requests, remembered choices and return to login.
- Depends on: the kiosk interaction and shared form steps needed by the case.
- Default settings: `gpt-5.6-sol` / `high`.
- Customer scope: E2E-017/018 and kiosk portions of E2E-013/014/015.
- Work:
  1. Select children and approvers, switch children and observe loading,
     disabled control, no-child/no-approver and ineligible states. Establish
     unrelated account fixtures through accepted setup.
  2. Exercise representative duration validation, cancelled/rejected approval,
     retry and both soft-app choices through the real prompt. Observe messages,
     retained selections, later child login and app use; no broker/grant reads.
  3. Use cancel/Escape and successful approval. Observe the required confirmation
     and return to GDM, distinct from the overlay's return to the desktop.
  4. Change choices in kiosk, visit the child overlay and return. Observe per-child
     remembered choices and independently remembered mute settings.
- Verification: execute complete variants, retain visible evidence and normal
  cleanup, and run affected shared-form regressions in both modes.
- Completion criteria: selection, request outcomes, cross-surface persistence
  and every declared exit path are proven by customer use.
