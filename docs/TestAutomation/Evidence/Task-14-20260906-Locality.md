# Task 14: locality readiness resolved

Scope: development host and existing guarded `ubuntu26.04` VM. The independent
administrator eligibility case now passes. Task 14 remains incomplete for its
remote-account fixture and final authorization-area acceptance.

## Result and implementation

`test_administrator_eligibility_predicates` now re-resolves the public
AccountsService object and observes its predicates until `LocalAccount` becomes
true, with a ten-second deadline and 100 ms polling interval. It records initial,
changed and terminal observations as predicate booleans and elapsed seconds,
without usernames, UIDs or credentials. Independent eligibility assertions remain
strict. No production code changed in this slice; the fixture change activates
on the next test invocation.

Installed evidence resolves the previous uncertainty: the unsafe-name
administrator was nonlocal at **0.028 s**, then local at **0.524 s**. Throughout,
it was an unlocked, interactive, non-system administrator with matching NSS
properties and an unsafe username. AccountsService's upstream
[reload implementation](https://gitlab.freedesktop.org/accountsservice/accountsservice/-/blob/23.13.9/src/daemon.c)
schedules passwd/shadow reloads after 500 ms; this corroborates the observed
delay but does not replace installed evidence.

Both unsafe-name and noninteractive administrator exclusions passed discovery
checks from parent, child and kiosk. Direct requests on child and kiosk returned
`AccessDenied`, not `InvalidRequest`, and preferences, filters, limits and grants
remained unchanged across all seven ordinary role accounts. This is a complete
pass of the combined case that previously failed fixture setup. Earlier failed
attempts remain preserved in [the prior evidence](Task-14-2026-09-06-Eligibility.md).

## Verification and provenance

One discriminating VM attempt in this slice; no unchanged rerun:

```sh
make build-test-artifacts OUTPUT_DIR=/tmp/onpc-task14-20260906-locality
pkexec /usr/local/libexec/onpc-test-runner system --artifacts /tmp/onpc-task14-20260906-locality --area authorization --test test_administrator_eligibility_predicates
```

Build session **58571** exited 0; VM session **97045** exited 0. Evidence:
`/tmp/onpc-system-f_co2838/evidence`, including `guest/authorization.xml` for
timed observations and `result.json` for exact expected/executed identities.
All **five executions** passed: one eligibility case and four package/reboot
prerequisites. Product, infrastructure, collection and cleanup all passed.
This selected result is partial; no final full-area or release pass is claimed.

| Input | SHA-256 |
| --- | --- |
| Source | `8e613f999255656676b7bf6bbc8cb0173a5ce3f1d002b016497af8c00b33e272` |
| Selected tests/helpers | `02dd0adc072ab0bebf002047242c16b3978b2624d509c4bd13979f4aac608728` |
| Package | `6e4d094c35692bc9df9b6aa1fa96277741f4ef93198d242f6ff15e0d1443f0fd` |
| Stable fixtures | `1a2e4e731d822cb31cf901ffcbbec617f588701b40edd9e65ccf486ad6379d43` |

Local verification: **30** runner/caller/agent cleanup checks; **88** runner
tests; host-safe exact selector collection; **19 + 3 subtests** local cleanup
checks. Dispatcher additionally passed **175 + 3 subtests** before VM mutation.
`make check`, session **47960**, exited 0: **1,287 unit/contract + 17 component**
tests, traceability, syntax and source checks. `git diff --check` passed.

| Preparation | Bootstrap | Install | Reboot | Tests | Collection | Cleanup |
| --- | --- | --- | --- | --- | --- | --- |
| 71.7 s | 42.2 s | 50.7 s | 19.6 s | 41.1 s | 1.6 s | 100.8 s |

Baseline restored; final `virsh ... domstate ubuntu26.04` reports **shut off**.
All owned commands completed. Only evidence/handoff documentation followed
the successful VM run. Earlier working-tree changes were preserved; no commit.

## Next slice

Implement real remote NSS fixture provisioning in the existing guarded VM,
then prove public AccountsService locality and broker exclusion. Start with the
existing bootstrap/provisioning interfaces and public LDAP/SSSD integration;
`CacheUser` requires the remote identity to resolve through NSS first. Do not
reopen completed name, locality, rename or method-audit investigations.
No remote fixture code or runtime coverage is claimed by this slice.

Next settings: **`gpt-5.6-sol` / `high`**; model: keep; effort: raise relative
to the prior handoff. The readiness question is solved; designing a real remote
identity fixture crosses NSS, AccountsService and guarded provisioning and
needs more reasoning. Keep the workhorse model for the bounded fixture slice.
