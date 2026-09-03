### Task 23 — Automate child-overlay request and approval scenarios

- Complexity: very high. The scenario includes a real system authentication
  prompt and atomic policy/time changes.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `xhigh`
- Objective: prove a signed-in child can request access without gaining reusable
  authority.
- Work:
  1. Open the request overlay from the child panel and verify the child identity
     is fixed and only eligible approving parents appear.
  2. Exercise predefined, rest-of-day, minimum, maximum, fractional, and invalid
     custom durations; prove invalid input never invokes Polkit.
  3. Select each eligible parent and verify the system prompt is restricted to
     exactly that parent and displays child, duration, and soft-app choice.
  4. Exercise authentication cancellation and a rejected password, then retry
     successfully without losing the form choices or consuming the rate interval.
  5. Approve without soft apps and prove blocked child apps close before time is
     active while unrelated apps remain.
  6. Approve with soft apps and prove open apps remain, hard launches remain
     blocked, soft launches work, and natural expiry restores soft blocks.
  7. Attempt rapid duplicate submission and prove exactly one grant transaction.
  8. Verify Escape, explicit cancel, success confirmation, automatic close,
     remembered shared choices, child-only mute value, and post-close countdown
     refresh.
  9. Prove the child has no reusable Polkit authorization or management access.
  10. Update child-request and approval requirement mappings.
- Verification:
  - Run denial/cancel and approval cases from separate fresh overlays.
  - Correlate UI results, correlation IDs, process evidence, AppFilter,
    ActiveExtension, and logs.
  - Run `make check-e2e` for this scenario, `make check`, and `git diff --check`.
- Completion criteria: child-overlay requests satisfy identity, authentication,
  transaction, exit, persistence, and least-authority requirements.

