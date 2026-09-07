# Task 14: current authorization area passed — 2026-09-06

Scope: development host and the existing guarded `ubuntu26.04` VM. This session
completed the previously pending kiosk and first authenticated revalidation
checks, then verified the remaining already-implemented variants together.
This is acceptance of the current registered area, not complete Task 14 or
release acceptance. No product, helper, test-source or host-setup changes were
needed; prior working-tree changes were preserved.

## Observed boundaries

- Child and kiosk callers: deliberate wrong-password denial without writes,
  successful selected-parent authentication and a real grant, continued denial
  of AccountsService role changes and broker management operations, and
  preservation of other accounts.
- All six live-state variants: child-role, approver-role and preference mutations
  on child/kiosk surfaces. Each mutation was visible before password submission;
  authentication succeeded, but broker revalidation denied the request and
  preserved the state recorded after the intentional mutation.
- The full current method/role, cross-account, private-preference, component-log,
  account discovery/icon, ineligible caller/target/approver, and persistent
  changed-role assertions ran alongside those authentication cases.

The area JUnit contains ten authentication records: six successful challenges
for requests subsequently denied by broker revalidation, and two wrong-password
denials followed by two successful grants. Exported redacted broker logs
corroborate request denials, both grants and subsequent management denials.
No raw terminal output or credentials were exported by this session.

## Inputs and commands

One fresh build completed and verified:

```sh
make build-test-artifacts OUTPUT_DIR=/tmp/onpc-task14-20260906-kiosk-revalidation
```

All three runs used that artifact directory with
`pkexec make -C /Data/Code/PST/parent-control check-system`,
`AREA=authorization`, and the selection below. Host-safe `LIST=1` confirmed each
closure. Before each guarded operation, the isolated runner, caller and agent
cleanup-safety modules passed **30 tests**. No guest pytest ran on the host.

| Run | `TEST` selection | Exec session / exit | Evidence directory | Exact executions |
| --- | --- | --- | --- | --- |
| Kiosk | `test_real_selected_parent_authentication[kiosk]` | 9927 / 0 | `/tmp/onpc-system-jqrp_cn3/evidence` | 5 passed |
| First revalidation | `test_authenticated_request_revalidates_live_state[child-role-child1]` | 19869 / 0 | `/tmp/onpc-system-n33_90rk/evidence` | 5 passed |
| Current area | omitted | 4978 / 0 | `/tmp/onpc-system-tht9nj_s/evidence` | 225 passed |

The area has 221 authorization cases and four installation/reboot prerequisite
executions. All three runs passed product, infrastructure, collection and cleanup
outcomes, with no failures, errors, skips, missing, additional or duplicate case
identities. The selected runs first established the two pending boundaries;
the area run then exercised the remaining variants and interactions between
cases. It was not a repeated stability qualification or speculative retry.

All runs record revision `70e16c080564d8b83cc4b8d605fece01d1028290` plus the
captured working tree (345 source files):

- Source SHA-256: `91d76f509821b0f6d1bbbe73673088280230444ff959855811130820fe5d1164`
- Package SHA-256: `11fe09f10b3921ca6d5718a8311ddd5d233e7429bdc76865d2456289a18896b3`
- Fixture SHA-256: `1a2e4e731d822cb31cf901ffcbbec617f588701b40edd9e65ccf486ad6379d43`

| SHA-256 | Kiosk | First revalidation | Current area |
| --- | --- | --- | --- |
| Selected inputs | `681e81f68c42a2560d5a3afb0116cf0524bf78f7f17d6e8b07a0ab524c627730` | `a10e2375e92cbec0fca2e6c4f475bdf216a780249b348c62374cd5e5e142d926` | `770d6a187d4e1f4e7dee35c6b3c364e8e290c30a927302ef2c72476ac79ce57d` |
| Authorization XML | `fb5afa61fbbaa45f79ff654688d981d41b363055ff7c523a24707e599444cfe0` | `bc561b9f60a7a95668d36e2fe59e07c9c5deeb93cddaf1b8b025babc839c005d` | `afea6e79a270c55c8c9f8d91b28557a8d961086875185543c95332d389fae143` |
| Aggregate result | `15b0ff1c5cc5fcb396550f7d5eb727bd651d2311e012c0c842f7e9de3105ff2b` | `f35e52ff9327defc9971c66c84ef1cd0dce9bb67d7e16b8701345612dc2f3d9d` | `172a1bc6da3e0f3d54b917c8ee9293ebb7f5b160e1fe776a5b5adba5e46e333d` |

## Audit, cost and final state

The read-only `/tmp/onpc-task14-kiosk-revalidation-audit.py` reconciles expected,
reported and actual phase/case JUnit identities, pass counts, per-case password
records, independent outcomes and completed cleanup. It audited all three runs.
It is an implementation evidence utility, not a new daily suite requirement.

| Stage seconds | Kiosk | First revalidation | Current area |
| --- | --- | --- | --- |
| Preparation | 71.812 | 68.607 | 64.534 |
| Bootstrap | 48.938 | 42.938 | 45.491 |
| Install | 49.172 | 50.530 | 49.732 |
| Reboot | 19.078 | 19.622 | 21.171 |
| Tests | 39.709 | 37.016 | 124.396 |
| Collection | 1.594 | 1.595 | 2.121 |
| Cleanup | 103.118 | 101.661 | 101.278 |

Runner totals are approximately 5.6, 5.4 and 6.8 minutes. Host authentication
waits, inspection and documentation are additional. After the two focused
passes, the shared helper was sufficiently proven to batch the existing area;
this avoided a separate VM cycle/session for each remaining variant. No
model/context telemetry was available. No new problem was opened after the
area result. Unchanged code checks were not repeated merely for a new session;
the [prior record](Task-14-2026-09-06.md) retains them and the original failures.

All owned commands exited with status 0. Baseline/domain restoration and host
preservation passed, and the final read-only domain check returned `shut off`.
No command or VM operation is pending. Subsequent repository edits document
these results only; final documentation links and `git diff --check` passed.

Task 14 stays unchecked: root method permissions, stale/deleted identities,
remaining selected identity/eligibility changes, requester-disconnect completion,
and final requirement/matrix review remain. Continue with the
[active handoff](../Task-14.md#continuation-handoff--2026-09-06-incomplete).
