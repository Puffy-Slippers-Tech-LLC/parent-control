# Task 14: independent administrator eligibility

Scope: development host and the existing guarded `ubuntu26.04` VM. Task 14
remains incomplete. This session delivered a broker fix and verified installed
noninteractive-administrator assertions; the combined new case still fails its
unsafe-name fixture precondition. No complete authorization or release pass is
claimed for the final inputs.

## Delivered

The specification requires interactive approvers even when selected outside
discovery. Previously the adapter filtered noninteractive shells only while
enumerating users; direct UID lookup omitted that information. `UserAccount`
now carries `is_interactive` from the current public AccountsService `Shell`
property. The broker requires it during approver selection and revalidation.
Missing shell properties fail closed. Existing management authorization is
unchanged. Adapter tests cover missing/empty, false/nologin and interactive
shells; core tests prove both request surfaces reject before Polkit or writes.

The installed case creates an unlocked local administrator with a valid shell,
proves it appears in discovery, changes only its shell with public `SetShell`,
and records that account type, locality, system status and lock state remain
eligible. Parent, child and kiosk discovery exclude it; child and kiosk direct
requests return `AccessDenied`, with preferences, filters, limits and grants
unchanged across the seven ordinary role accounts. These assertions completed
in attempts 2 and 3. The case is still one combined JUnit identity, so those
completed assertions do not turn its later fixture failure into a passing case.

The unsafe-name fixture now uses supported `useradd` directly, a generated
in-memory password and public AccountsService lookups/setters. Its assertions
retain the exact independent predicates and distinguish `AccessDenied` from
`InvalidRequest`. The selector registers fixture-password prerequisites.

Activation: existing broker payload changes are `process-restart`; test changes
activate on the next invocation. No new system integration, saved-data migration,
host installation, VM, overlay or baseline was introduced. Earlier working-tree
changes were preserved; this session made no commit.

## Experiments and outcomes

1. `/tmp/onpc-system-ofxq7i2n/evidence`: full authorization area, **227 existing
   authorization cases and four package/reboot cases passed**. New case failed
   before creating an account: AccountsService invokes `adduser`, which rejected
   the 33-byte fixture name (32-byte maximum). The service journal and command
   stderr establish this cause. Corrected names and added an explicit length
   guard. Build **39200** exited 0; VM **59960** exited 1.
2. `/tmp/onpc-system-hlkynm8m/evidence`: focused corrected case plus four
   prerequisites. Noninteractive assertions passed. The public unsafe-name rename
   succeeded and exposed the intended properties, but AccountsService then logged
   a duplicate-object export error. Direct selection returned `InvalidRequest`,
   indicating unavailable identity rather than username exclusion. The collector
   retained the original identity before renaming for redaction. Four prerequisites
   passed; the combined case failed. Build **58704** exited 0; VM **56197** exited 1.
3. `/tmp/onpc-system-vdpfos_4/evidence`: focused direct-creation correction,
   justified by the duplicate-object diagnostic. Public `FindUserById` now resolves
   the correct object. Noninteractive assertions again passed. The unsafe-name
   administrator has `AccountType=1`, `SystemAccount=false`, `Locked=false`, an
   interactive shell, unsafe username and matching NSS properties, but
   **`LocalAccount=false`**. The strict fixture precondition failed before its
   discovery/direct-request assertions. Do not claim independent unsafe-name
   coverage. Four prerequisites passed, combined case failed. Build **62217**
   exited 0; VM **18129** exited 1.

All attempts retain their failures. Infrastructure, collection and cleanup passed;
the runner attributes failed pytest cases to its product domain, although these
three failures are diagnosed as fixture/dependency issues. Raw logs were not
modified. Evidence was inspected with the approved artifact helper.

Commands (artifact suffixes `-v2` and `-v3` identify corrected inputs):

```sh
PYTHONPATH=broker:kiosk /usr/bin/python3 -B -m pytest tests/unit/test_adapters.py tests/unit/test_core.py tests/unit/test_system_runner.py -q
/usr/bin/python3 -B -m pytest tests/unit/test_system_runner_cleanup_safety.py tests/unit/test_system_caller_cleanup_safety.py tests/unit/test_system_agent_cleanup_safety.py -q
make build-test-artifacts OUTPUT_DIR=/tmp/onpc-task14-20260906-eligibility
pkexec /usr/local/libexec/onpc-test-runner system --artifacts /tmp/onpc-task14-20260906-eligibility --area authorization
pkexec /usr/local/libexec/onpc-test-runner system --artifacts /tmp/onpc-task14-20260906-eligibility-v3 --area authorization --test test_administrator_eligibility_predicates
make check
git diff --check
```

Focused checks: **178 passed, 27 subtests passed**. An initial local invocation
without the repository's `PYTHONPATH` failed collection; the corrected invocation
above passed. Runner/caller/agent cleanup regressions: **30 passed** before each
VM attempt. Each installed dispatcher additionally passed **175 tests / 3 subtests**.
UI/preview/host cleanup prerequisites: **19 passed / 3 subtests** before local
aggregate checks. Final `make check`, session **56063**, exited 0:
**1,287 unit/contract and 17 private-D-Bus component tests passed**, plus stage
traceability, syntax and source guards. All seven final selected hashes match
the checkout. Only handoff/design documentation followed the final VM attempt.

| Final input | SHA-256 |
| --- | --- |
| Source | `3492703495870ea217b5ff00e329ea3bd8cfeac26dc80fc1ede54a75fa32e0aa` |
| Selected tests/helpers | `74c0b25118eb607f1b45c5ee8a16f2e4f73caff807f657ab3ba65a9ccf766561` |
| Package (same in all attempts) | `6e4d094c35692bc9df9b6aa1fa96277741f4ef93198d242f6ff15e0d1443f0fd` |
| Stable fixtures | `1a2e4e731d822cb31cf901ffcbbec617f588701b40edd9e65ccf486ad6379d43` |

Final attempt timing: preparation 71.3 s, bootstrap 45.1 s, installation 50.5 s,
reboot 19.6 s, tests 39.2 s, collection 1.7 s, cleanup 98.8 s. The original slice
exceeded its estimate to diagnose distinct fixture failures and complete owned
operations. No fourth speculative attempt was launched. Final baseline restored,
VM **shut off**, all commands finished.

## Exact continuation

First observe public lookup/property readiness over a bounded deadline after
direct account creation. Determine whether `LocalAccount=false` is a delayed
local-account reload or stable classification. Existing observations are immediate,
so they do not distinguish these explanations. Record only predicate values and
timings. Keep strict locality and all other eligibility assertions; do not accept
`InvalidRequest` as the username exclusion. Do not retry the failed rename route
or redo the completed method audit. Qualify the corrected case with its exact
selector before broader acceptance.

Real remote-account coverage remains unimplemented. The installed public
`org.freedesktop.Accounts.xml` documents `CacheUser` for remote usernames that NSS
already resolves; `LocalAccount` is read-only. A supported next integration path
is a real LDAP/SSSD fixture, using the existing guarded VM and test provisioning,
with explicit NSS and AccountsService observations. Ubuntu documents
[SSSD with LDAP](https://documentation.ubuntu.com/server/how-to/sssd/with-ldap/index.html).
This is a proposed fixture design, not runtime evidence or a reason to create a
new VM/baseline. Do not replace it with private AccountsService cache edits or mocks.

Next settings: **`gpt-5.6-sol` / `medium`**, keep both. The immediate next problem
is bounded locality/readiness observation using proven helpers. Reassess effort
when beginning the separate LDAP/SSSD integration design.
