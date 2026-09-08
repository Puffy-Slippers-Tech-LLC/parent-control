# Task 19A — real fixture GDM authentication

**Solid progress:** the previously missing authentication checkpoint now has a
complete guarded live pass. The worker selects the canonical fixture parent by
name, refuses its password needle on two inappropriate screens, enters the fresh
fixture password through the public secret-safe API, and obtains independent
confirmation of the intended active local graphical session. Source, host,
collection and baseline cleanup passed. Task 19A remains open for public serial
execution, launcher/scenario-evidence integration and final acceptance.

## Implemented boundary

The maintained distribution now contains three reviewed PNG/JSON pairs:
`onpc-gdm-parent-account`, `onpc-gdm-other-parent-account`, and
`onpc-gdm-parent-masked-password`. They retain only synthetic fixture pixels.
The password needle jointly matches the fixture identity, empty field/visibility
control and focus outline, avoiding the blinking caret. Every area requires
100% matching. No coordinate or unrelated-account fallback permits password input.

The credential qualification first checks that the password needle rejects the
account list, selects the other fixture parent by its own needle, and verifies
that this wrong identity also refuses. It then selects the intended parent and
uses the existing `onpc_password::enter_password('parent', 'gdm')` helper.
The helper's public `assert_screen` succeeds immediately before `type_password`;
the distribution submits Return and requests the separate `authenticated` stage.

`ReadOnlyObservations.read('parent-session')` runs a fixed read-only program. It
resolves the actual fixture UID and requires exactly one active local graphical
`gdm-password` user session. Wrong accounts, SSH/TTY/remote/inactive sessions,
duplicates and extra user sessions cannot pass; only the root SSH observer is
exempted. It returns fixed safe fields, without names or raw session identifiers.
Missing authentication cannot pass the credential worker's stage reconciliation.
Explicit post-password screenshot uploads are refused. Raw worker logs, vars
and automatic captures remain private and unapproved for export; the frozen
secret registry continues to protect both structured evidence collectors.

This changes development test behavior on next invocation (`none` activation).
No product configuration, data schema, host setup or accepted baseline changed.
Only parent GDM input is qualified here; other roles and surfaces need their own
reviewed positive/negative matches. All 156 scenario variants remain pending.

## Experiments and retained evidence

| Attempt | Command / handle | Outcome | Preparation / test / cleanup / total seconds |
| --- | --- | --- | --- |
| Account matching 1 | `tools/run-tests integration check_graphical_smoke` / 43429 | Failed before selection/password; baseline/source/host preserved | 249.518 / 132.765 / 72.424 / 587.208 |
| Account matching 2, corrected pixels | Same command / 40424 | Passed selection, empty fixture prompt capture and Escape return; full preservation | 250.343 / 107.291 / 72.332 / 560.444 |
| Authentication 1 | `tools/run-tests integration check_graphical_credentials` / 1649 | Passed both wrong-prompt refusals, actual login, independent session proof and cleanup | 393.762 / 298.848 / 72.947 / 908.051 |

The first attempt scored 96% even though direct pixel comparison showed that
the fixture label region was identical to the reference. Its needle masked
pixels exactly at the match rectangle's boundary. The
[upstream matcher](https://github.com/os-autoinst/os-autoinst/blob/master/ppmclibs/tinycv_impl.cc)
blurs neighboring pixels. Retaining a 16-pixel fixture margin corrected the
match: attempt 2 scored 100% with zero error. The threshold was not reduced.
This failure remains retained; the corrected run is a separate attempt.

Authentication's result module is `ok`, with zero dents and 42 seconds of
graphical test execution. Both account labels and all three password-prompt
regions scored 100%. Its two expected `check_screen` misses are recorded as
`unk`, followed by fixed `prompt-refusal` and `authentication` notes. The
controller's final stage records `fixture_role=parent`,
`active_local_graphical_session=true`, `unexpected_user_session=false`.
The existing bounded shutdown after login increased worker duration to 228.196
seconds; worker and callback cleanup both passed. These are outer cleanup
operations, never customer actions or in-journey baseline restores.

Root-private original results:

- First failure: `/tmp/onpc-graphical-smoke-xyqyy3t9/result.json`;
  checkpoints `/tmp/onpc-e2e-evidence-54usxgu0`;
  worker `/tmp/onpc-e2e-evidence-zfez2o8j/worker-result.json`.
- Corrected selection: `/tmp/onpc-graphical-smoke-bc864olp/result.json`;
  checkpoints `/tmp/onpc-e2e-evidence-pyf9pr56`;
  worker `/tmp/onpc-e2e-evidence-0elz1nxh/worker-result.json`.
- Authentication: `/tmp/onpc-graphical-smoke-u6yli1hl/result.json`;
  checkpoints `/tmp/onpc-e2e-evidence-t96id5nn`;
  worker `/tmp/onpc-e2e-evidence-xstf6qqz/worker-result.json`.

Both successful runs report infrastructure, collection and cleanup passed,
source/host preservation true and `lease_phase=complete`. Product was not run.
The authentication result contains the complete selected-file digest map.
Its distribution SHA-256 is
`c67a14aa7b38196457f175b6e3d8ef197bd44e8946abd1ab7627c0efae95a322`.

| Input | SHA-256 |
| --- | --- |
| First failed selection source | `804d480f7d72a2f8e65a3ac77f13440411c817bcda7f80d77f7851bce4b610ab` |
| Corrected selection source | `2308d0f33cf5e1c4c435e23099767c375e6fc0476650314e3ffad0333f6a4c56` |
| Authentication source | `e775191ad270c7f3a6604aa643377829a88b2a51edbba2645bce05470a1083b2` |
| Accepted baseline | `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5` |
| Parent account PNG | `ddd39364e5cea7676aeb744e9f59617699e6b504c10bcf9074c94bfff3683b54` |
| Other-parent account PNG | `001458fb9efd2802958e3944b5714b99eb77b68910131a809e62401b8df3e7f0` |
| Parent password PNG | `9ca8a684db0cc125f0064d13d75fa503e1b2e697b2b37f9ed1a76b80a6b371df` |

No package artifact was needed or nominated. Subsequent edits are documentation
and the credential entry point's descriptive docstring; runtime behavior and
needle bytes are unchanged from the authentication pass. A package-bearing
attempt must still obtain current verified artifacts.

## Checks, cleanup and forecast

Final focused selection: 218 passed in 0.93 seconds (72367), covering observation,
needle, graphical-controller, secret, worker and credential modules. Each live
dispatch independently ran isolated cleanup prerequisites: 339 tests plus three
subtests for attempt 1, then 343 plus three subtests for the corrected/authentication
attempts. There are 18 new host regression cases for the session probe and
authentication stage's success/refusal boundaries.

Final `make check` passed (89531): 2,334 unit/contracts in 43.81 seconds,
17 private-D-Bus components in 0.37 seconds, plus syntax and stage traceability.
`git diff --check` passed after the documentation updates.
All three VM command handles exited, with their original outcomes
preserved. `tools/test-vm status` returned `state=5`, `id=-1` after authentication.
Three private review exports and one derived temporary PNG were removed with
`tools/cleanup-screenshots`; original logs and captures were preserved. No
post-password capture was exported, and no operation needs recovery.

The three live attempts consumed 2,055.703 seconds (34.26 minutes), excluding
implementation, focused tests and review. This slice exceeded the initial
15–30-minute plan to fix and verify matching, review the real prompt, and close
actual authentication in the same session. No usage telemetry was available.

For **remaining Task 19A only**, plan approximately **3–5 further sessions /
4–8 hours**, with low confidence until serial execution is demonstrated. This
allocates 1–2 sessions to public console integration and its live command,
1–2 to launcher/scenario evidence wiring, and one to acceptance/corrections.
It is a planning range based on the remaining boundaries and observed run cost,
not a carried-forward completion promise. Next session must target an executed
harmless public serial command with evidence and cleanup, reusing the proven
credentials and login. Reassess the range after that checkpoint. Customer
scenario implementation and Task 19B are outside this estimate.
