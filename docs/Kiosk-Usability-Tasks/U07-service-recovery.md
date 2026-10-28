# U07 — Recover requests after a temporary service outage

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: U06.
Estimate: 45–90 min; session exception: one broker outage/restoration/request history per target.

Apply the [master contract](../Kiosk-Usability-Plan.md#per-task-acceptance-boundary).
Read the kiosk's startup/account/request callbacks, broker registration and
[recovery limits](../SystemDesign/Lifecycle.md#compatibility-and-recovery-boundary).
Discover existing broker owner-loss/retry operations and tests before adding any.

Use one temporary broker unavailability before a request is submitted. Preserve
safe unavailable feedback, bounded retry/exit and the first sanitized cause.
After service restoration, a supported retry or fresh entry must give a usable
request without reinstalling or manual state deletion. Fix demonstrated coupling
only; no generic dependency supervisor, cross-service outage matrix or unrelated
diagnostic-export project.

Observe no grant during outage, restored genuine approval with intended time
access and no duplicate/replayed approval. Host controls cover late callbacks,
deadline/cancellation and uncertain request results as applicable. Do not retry
an approval or mutation whose result is unknown. Run affected checks, required
backend review/build and owned restoration; close only U07.

## Selected history

Temporarily runtime-mask and stop the broker after the request form is ready,
before its single Request action, using the existing owned broker-fault helper.
Close the setup Parent window before switching to the station; reopen it after
restoration for independent time reads. Its own polling/error dialogs are outside
this request-only history.
Select Rest of the day before the fault so periodic estimates cannot introduce
an unrelated error. Require sanitized Request unavailable feedback and no grant.
Exit safely, restore the owned service, then enter afresh and make one genuine
75-second request with independent Parent time readback and no replayed grant.
No product change is currently indicated by source review.

Reuse the existing callback/single-use, cancellation and bounded-agent-wait host
controls. Add only the missing finite installed composition; do not add tests
of its test helpers. Run it on both declared targets, with owned fault restoration
and the maintained runner's final cleanup.
