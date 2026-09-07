# Task 14 coverage audit — 2026-09-06

This finite audit compares the 17-method interface in
[Broker](../../SystemDesign/Broker.md#broker-interface-and-roles) with
`tests/system/test_authorization.py`. Runtime outcomes belong to the acceptance
record; collection alone is not a pass.

## Method and role coverage

`test_method_role_matrix` invokes every method as child1, child2, parent1,
parent2, locked administrator, kiosk, and unrelated standard user (119 cells).
The unrelated standard user is an eligible child, not a fourth privilege role.
`test_root_method_permissions_and_approver_exclusion` covers all 17 root cells.
`test_ineligible_callers_cannot_use_broker` covers 34 noninteractive/system cells.

| Methods | Additional installed assertions beyond the role result |
| --- | --- |
| `ListManagedUsers`, `ListApprovers` | Post-install discovery, sorting, excluded local fixture roles, authoritative icons, deleted selections, live role changes; locked-parent exclusion during an active prompt added by this audit. |
| `GetOwnAccount` | Exact real caller UID, authoritative icon, changed caller role. |
| `GetPreferences`, `GetTimeStatus`, `CalculateRemainingTime`, `UpdateRequestPreferences`, `SetRequestMuted` | All three standard callers denied another child's target; target preferences unchanged. |
| `CalculateOwnRemainingTime`, `PrepareOwnSession` | Child-only method cells derive identity from the bus caller. Arithmetic and session reconciliation semantics belong to Tasks 16/17. |
| `ListApplications`, `SetPreferences`, `SetParentControl`, `RevokeOneTimeGrant` | Management-only cells, actual root preference/control changes, other-account state isolation, no management authority retained after successful child/kiosk authentication. App enforcement semantics belong to Task 15. |
| `RequestOwnAccess`, `RequestAccess` | Disabled-child denial; enabled-child authentication; both surfaces prove wrong-password denial and successful selected-parent grant; stale/deleted target and approver, authenticated role/preference changes, requester disconnect/cancellation and fresh approval; active-prompt approver locking added by this audit. |
| `LogEvent` | Every front-end role and root denied each other component and broker log. |

## Account and broker requirement mapping

| Requirement | Installed evidence and remaining scope |
| --- | --- |
| CORE-ACCOUNTS-001 | Management method cells, post-grant management denial, and real remote-administrator caller denial after correcting the broker locality check. Parent graphical launcher behavior remains E2E. |
| CORE-ACCOUNTS-002 | New local account discovery, sorting, local exclusions, authoritative icon/empty-icon changes, deleted-target disappearance. Real LDAP/SSSD standard-account discovery, direct-target and caller exclusion now pass; see [remote evidence](Task-14-20260906-Remote.md). |
| CORE-ACCOUNTS-003 | Eligible parent discovery, all registered ineligible selected-parent denials, root exclusion, changed/deleted approver, exact selected identity, active-prompt lock. Independent noninteractive and unsafe-name administrator discovery and direct-selection denial pass on child and kiosk with all other predicates true; see [eligibility evidence](Task-14-20260906-Locality.md). Real LDAP/SSSD administrator exclusion now passes both surfaces with every other eligibility predicate satisfied; see [remote evidence](Task-14-20260906-Remote.md). |
| CORE-ACCOUNTS-004 | Management, denial and approval snapshots of preferences, limits, grants and filters across all seven ordinary role accounts. Complete customer journeys remain E2E. |
| COMP-BROKER-001/002/004 | All method/role cells, real credential drop and system-bus dispatch, cross-child rejection, root policy, post-approval denial. Broad functional responsibilities in 001 extend beyond Task 14. |
| COMP-BROKER-003/007 | Stale/deleted selections, live caller role changes, both request surfaces' authenticated target/approver role and preference changes, disconnect/cancellation, selected-parent authentication, active-prompt lock. Locked-account PAM denial is distinct from successful authentication followed by broker revalidation. |
| COMP-BROKER-005 | Both child records denied direct reads for all seven front-end roles; direct write-open denial and unchanged record/state checks added by this audit. Record schema/identity validation is a separate obligation. |

Requirement file references for BROKER-001/003/007 now include the installed
suite. BROKER-002 (real caller identity) and BROKER-004 (method permissions) are
`covered` after the corrected full-area run. Other audited requirements remain
`planned` pending their complete required scope/layer; system assertions do not
satisfy an E2E requirement. See the
[runtime evidence](Task-14-2026-09-06-Coverage-Audit.md).

## Bounded result and remaining gaps

The documented method/role matrix has no unregistered cell. This session adds
direct write-access refusal and active-prompt lock denial on both surfaces.
It does not reopen previously qualified deletion/disconnect experiments.

Noninteractive, unsafe-name and remote administrator exclusions now pass through
real AccountsService and broker calls. The remote fixture uses OpenLDAP/SSSD,
with no private AccountsService edits or mocked installed evidence. The bounded
eligibility gaps are resolved. The final inputs passed the complete authorization
area in the [final acceptance](Task-14-20260906-Final-Acceptance.md); Task 14 is
accepted. E2E account requirements remain planned.
