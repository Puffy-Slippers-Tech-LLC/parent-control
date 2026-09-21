# Restore retained consumers and regressions

Apply the [shared contract](README.md). These are dependencies of migration
close-out, not permission to expand a unit/UI selection to all host coverage.
Source entry points are [accessible_ui.py](../../../tests/e2e/accessible_ui.py),
[ui_observations.py](../../../tests/e2e/ui_observations.py) and the existing
journey/worker for the selected retained case. Keep its complete assertions.

| Done | ID / budget | Requires | Bounded deliverable and measurable acceptance |
| --- | --- | --- | --- |
| [ ] | R01 / 50 min | G02, S01 | **Host Shell search:** resolve Overview/search and distinguish the Parent launchable result from a web suggestion. One query has exact readback and observed result focus before Enter; tests cover wrong owner, ambiguity, incomplete absence and uncertain input. Names may select only inside this provider adapter. |
| [ ] | R02 / 45 min | R01, G06, prepared VM; A01v if needed | **VM search:** real Parent search launches the owned Parent window once; a standard-account route independently observes the expected unavailable launcher. Empty/nonempty query, wrong-result refusal, complete absence and cleanup pass. Hidden launcher alone makes no execution-denial claim. |
| [ ] | R03 / 55 min | R01, G02 | **Host terminal:** bind the actual installed terminal and implement focused nonsecret command input, bounded existing help/denial projections and close/return. Short ID/official-source lookup is optional. Tests refuse wrong window, unfocused recipient, command echo as result and replay after uncertain input. Package authentication stays in L01. |
| [ ] | R04 / 55 min | R03, R02, prepared VM | **VM terminal:** execute retained case 6 in full through `tools/run-tests e2e --id '6'`; require explicit management denial, closure/return, evidence/cleanup and coverage refresh. A missing executable binding is repaired without omitting recipe assertions. |
| [ ] | R05 / 55 min | R02 | **Host license viewer:** select the actual default handler and implement document identity/content, active close and return. Reuse Text Editor work if that is the real handler; no need to support all viewers. Tests reject a different document, ambiguous window, empty/unrelated content and uncertain close. |
| [ ] | R06 / 45 min | R03, R04, prepared VM | **VM help:** execute retained case 193 in full; both registered commands/manuals yield their required content and normal terminal return. Evidence, cleanup and coverage refresh pass. |
| [ ] | R07 / 50 min | G01, G04, G06; retained case 1's serial/return bindings; prepared VM | **VM case 1:** run `tools/run-tests e2e --id '1'`; require its complete graphical/serial recipe, capture reconciliation, collection, cleanup and coverage refresh. If a retired return path blocks it, implement its public GDM replacement as a separate bounded task first. Do not restore generic pixels or silently substitute graphical VT6. |
| [ ] | R08 / 50 min | G06, R02; retained case 3 bindings; prepared VM | **VM case 3:** run exact case 3 with all existing public results, evidence, cleanup and coverage refresh. Missing owned-ID qualification is a separate named blocker. |
| [ ] | R09 / 50 min | G06, R02; retained case 4 bindings; prepared VM | **VM case 4:** run exact case 4 with all existing public results, evidence, cleanup and coverage refresh. Do not treat launcher absence as terminal denial. |
| [ ] | R10 / 50 min | G06, R02; retained case 5 bindings; prepared VM | **VM case 5:** run exact case 5, including its declared discovery/profile setup and public comparisons; evidence, cleanup and coverage refresh pass. No saved-policy shortcut. |
| [ ] | R11 / 50 min | G06, R02, R05; retained case 151 bindings; prepared VM | **VM case 151:** read the actual license through its viewer and complete all retained About/Parent return assertions. Evidence, cleanup and coverage refresh pass. This is also the installed qualification of R05. |

For R08–R11, use `tools/run-tests e2e --id '<exact numeric case>'`, replacing the
placeholder with that row's number. Each is its own task/attempt. Reuse valid
unchanged evidence; do not rerun an already passing case merely to update prose.
If later source changes invalidate that evidence, rerun only affected checks.

All five required cases **1, 3, 4, 5, 151** must pass for shared
GDM/secret/routing close-out. Cases 6 and 193 additionally protect changed
terminal routes. A current block does not erase retained scenario registrations
or make a partial recipe acceptable. Missing consumer implementation discovered
here becomes a concrete, at-most-one-hour prerequisite task, not an unbounded
repair hidden in the live-run row.
