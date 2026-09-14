# Task 23 — Child-overlay customer requests

Follow [E2E-Coverage.md](E2E-Coverage.md). Use the actual child panel, installed
shared form and real system authentication prompt. Observe choices, messages,
countdown and app access. No grant/filter/property reads, broker calls,
correlation IDs or transaction tracing are customer assertions.

## Implementation slices

Reuse accepted graphical input and real request interactions from the first
consumer. Helpers accept the surface explicitly so Task 24 can reuse them.
Neither a completed internal authorization matrix nor another task's full
customer matrix is a prerequisite. Complete one approval or rejection/retry
journey before adding variants.

## Task 23A

- Title: Child-overlay approval, cancellation and retry.
- Depends on: verified installed setup and a real child session with usable time.
- Default settings: `gpt-5.6-sol` / `high`.
- Customer scope: E2E-012 and the overlay part of E2E-013.
- Work:
  1. Open the overlay from the panel. Observe one form, the fixed child, eligible
     parents, selected duration and soft-app choice. Select each supported parent
     identity and observe the real prompt naming the intended approver.
  2. Cancel authentication or enter a rejected password. Observe the message,
     preserved selections and continued app restriction. Retry through the real
     prompt and observe successful confirmation and usable time.
  3. Approve with and without soft apps. Use the desktop and attempt allowed,
     hard and soft launches to observe the chosen behavior. Where approval
     should close existing apps, observe their windows after approval.
  4. Try repeated submission through normal clicks. Observe the documented UI
     handling, confirmation and displayed time. Do not claim an internally
     exactly-once commit from screens.
  5. Reopen a request and observe that real authentication is still needed.
     Direct authorization attacks remain existing/separate system tests.
- Verification: run complete declared approval and rejection/retry variants,
  inspect visible evidence, retain existing safety/cleanup and affected checks.
- Completion criteria: prompt identity, success, rejection/cancellation, retry
  and app-use choices have passing customer evidence. No internal atomicity or
  ordering proof is a completion requirement.

## Task 23B

- Title: Overlay choices, validation and exit.
- Depends on: only the working overlay interaction needed by each case.
- Default settings: `gpt-5.6-sol` / `high`; reassess routine case expansion.
- Customer scope: overlay portions of E2E-014/015/018.
- Work:
  1. Use predefined, custom and rest-of-day choices. Try representative minimum,
     maximum, fractional and invalid values; observe feedback and disabled
     submission. Leave existing exhaustive local form tests intact.
  2. Reopen the panel entry, use Escape/cancel, and complete a successful request.
     Observe single-overlay behavior, confirmation, close and countdown refresh.
  3. Reopen the form to verify remembered choices for each child. Observe mute
     choices through the UI; do not read shared preferences. Task 24B owns the
     full kiosk/overlay round trip.
- Verification: complete the selected visible flows, run affected shared-form
  regressions in both modes if shared code changes, and retain normal cleanup.
- Completion criteria: declared choices, validation and exit paths pass without
  inspecting storage or authentication internals.
