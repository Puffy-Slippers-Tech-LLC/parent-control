# Reliable kiosk entry with explicit confinement

Task queue: [Ordered task queue](Kiosk-Prompt-Queue.md).
Next task: **R01 — [Settle the admission and confinement contract](Kiosk-Prompt-Tasks/R01-contract.md)**.

## Outcome

Selecting the request station must open a usable request form without a kiosk
password, including on supported computers with unusual, unexpected configuration.
The child must not obtain a normal desktop, terminal, SSH login or unrestricted
application-launch route through the kiosk. Parent approval and broker
authorization remain effective.

The developer replaces the earlier exception-by-exception repair programme with
this design change. Unknown host configuration is tolerated by default. Every
unexpected kiosk-entry rejection on an ordinary supported configuration is a
product blocker, even if a helper calls it an intentional refusal or the runner
classifies the attempt as infrastructure failure. Planning grants no
implementation or installed acceptance.

Product requirements remain in the [specification](Specification.md) and
[confinement owner](SystemDesign/Kiosk-Confinement.md). That owner distinguishes
current enforcement from the prospective target. This plan owns implementation
order, finite acceptance and disposition of the old work.

## Target design

Use a small dedicated kiosk startup path, isolated account and narrowly justified
OS enforcement. Keep the established kiosk compositor and request form initially.
Remove host-wide cleanliness requirements and the obligation to reconstruct a
retained manager's filesystem at each login. Reuse existing mechanisms only when
they directly serve the smaller boundary.

The policy is **blacklist-led compatibility with explicit escape barriers**:
enumerate prohibited capabilities and reachable escape routes; tolerate other
host variation. It is not a blacklist of executable basenames. Renaming a program
must not change whether an exposed route can launch a desktop or shell. Neither
a universal executable allowlist nor an exact image of the host's `/usr` is a
design requirement. Unknown applications and services on the host neither veto
entry nor automatically acquire a kiosk launch route.

The ordinary attacker is a non-administrator child operating the exposed kiosk,
with files and settings in their own account. Do not start by assuming that child
already controls the kiosk UID, its protected startup files or arbitrary code
execution inside it. Stronger engineering fixtures remain useful where they
exercise a reachable path or a regression introduced by this change; they do not
automatically justify more admission predicates. Name-based blocking alone does
not establish containment after arbitrary-code compromise.

| Current dependency to challenge | Replacement requirement |
| --- | --- |
| Ambient directory inventories, sibling ownership, filename encoding and whole-layout identity | Unrelated host content has no admission vote. Do not enumerate it to establish safety. Constrain only resources and search paths actually consumed by the kiosk. |
| Exact identity of artwork, fonts, licenses, translations and old release notes | Provide defaults or disable presentation effects. These resources cannot invalidate a healthy request session. Executable Python/JS, units, plugin configuration and authorization data are not cosmetic. |
| Retained manager as the source of another reconstructed filesystem view | One clear lifecycle owner. Healthy reuse is an optimization; an owned stale or failed instance has bounded safe renewal. Neither the same PID nor the same view across visits is a customer requirement. |
| Reject every unknown PAM module, harmless text change or optional desktop service | Preserve effective account/access policy and ordinary accounts. Reduce coupling to vendor callbacks and isolate unnecessary activation. An unknown name or syntax variation alone is not evidence of an escape. |
| Repeated startup proofs and strict caller-environment assumptions | Establish the necessary boundary at its authority; initialize newly owned state explicitly and tolerate valid inherited groups, umasks and timing variation. Retain only rechecks addressing a concrete race. |
| Reboot or manual repair for every mismatch | Retry transient dependencies and renew owned stale state within declared bounds. Routine unrelated changes and cosmetic drift must not require reboot. Genuine package/security activation requirements remain separately justified. |

R01 chooses the exact supported implementation before replacement work. Prefer
existing public GNOME, systemd, logind, PAM and MAC interfaces. A prepared runtime,
if needed, contains only justified consumers and is reconciled outside the normal
login critical path where possible. Do not replace the current machinery with
another general-purpose image/generation framework. Read-only mounts alone do
not prove backing-file lifetime or executable safety. Reduce a current boundary
only after its smaller replacement passes the actual first-exec, service and
lifecycle proof on both platforms.

## Allow, recover and reject

This is the required decision policy, not a claim about current implementation.
R01 records exact predicates and observations in the owning design; R09 binds
each row to executable checks without creating a second policy table.

| Situation | Required disposition | Reason and limit |
| --- | --- | --- |
| Unknown installed application, benign service, extra directory, strange filename, unrelated permissions or metadata | **Allow entry** | Unrelated host state is outside the kiosk decision. Never classify “unrecognized” as hostile. |
| Missing artwork/font/catalogue, broken optional audio/notification/rich-reporting dependency | **Allow with a fallback** | The core form, child selection and genuine parent authentication remain usable. Code-loading and authorization inputs need separate classification. |
| Valid distro aliases, local configuration, supported PAM variation or inherited GDM credentials | **Allow entry** | Validate needed behavior and authority, not resemblance to a clean VM. Isolate an unnecessary integration rather than rejecting the session. |
| Slow/restarting dependency, temporary lock contention or incomplete owned startup | **Bounded wait/recovery** | Preserve the attempt where safe. Use measured deadlines, not tight clean-VM timing assumptions; no busy loop or unlimited retries. |
| Owned stale/failed kiosk infrastructure with no active public session | **Bounded renewal and entry** | Serialize with login; prove ownership, stop only that instance, preserve data, then retry once. Never kill by guessed PID or blanket UID. |
| Healthy concurrent kiosk visit or uncertain/foreign infrastructure | **Preserve it; resolve safely** | Do not terminate another session. R01 defines attach/wait/clear conflict handling; unexplained normal-use conflicts cannot be waived as passing availability. |
| Selecting an ordinary desktop, console/SSH login as the kiosk, or a reachable kiosk action launching a terminal/general application handler | **Block that route** | Explicit defense of the dedicated request-only account. Keep the valid kiosk route available; an optional action refusal must not abort the entire session. |
| Child-controlled startup/module/plugin/activation input that would actually be consumed | **Exclude that input or block the affected route** | Prove the path is reachable and attacker-controlled. Unrelated files elsewhere cannot cause rejection. |
| Wrong/privileged/foreign identity, attacker-writable essential code, or inability to establish actual confinement | **Do not start an unrestricted session** | Repair/reselect safe product-owned state where possible. Remaining failure is a precise security/setup fault, not proof of a breach attempt or successful compatibility. |
| Explicit administrator access denial, expired account, denied or cancelled parent authentication | **Honor the policy/result** | Do not weaken other users' authentication or silently override administrative policy. Parent denial leaves the request form confined and usable. |
| Core broker/approval service remains unavailable after recovery | **Explain the unavailable operation; retain safe retry/exit** | An error-only surface is not acceptance for a fixture expected to complete requests. Never present an unexpected kiosk password as the remedy. |

Every retained hard-entry rejection needs a short ledger entry: trigger,
concrete reachable escape/privilege risk or explicit policy, why
exclusion/degradation/recovery is insufficient, positive normal-use control,
negative control, actionable customer explanation, sanitized diagnostic cause
and recovery result. Missing enforcement and administrative denial are not
attacks; diagnostics must say so. Optional failures and unknown configuration
must not collapse into those categories. An optional inventory, diagnostic or
freshness check failing does not establish that confinement is absent: identify
the actual required enforcement operation that failed before retaining a
hard-entry rejection.

## Acceptance

Both `onpc-Ubuntu26.04` and `onpc-Fedora44` must pass. This does not expand the
distribution/version support boundary. Normal configured systems, including
these variations, must reach the usable form without a kiosk password,
unrestricted fallback, administrator intervention or reboot solely to repair
ambient/non-security drift. Preparation success, native probes, process census
and error dialogs alone are not that result.

| Family | Finite positive and negative coverage |
| --- | --- |
| A — Unrelated host variation | Existing sibling cases plus extra applications, writable/non-root-owned unrelated siblings, non-UTF-8/control-character names, benign aliases and parent metadata changes. Unrelated entry counts cannot exhaust an admission scan budget. |
| B — Optional data and services | Missing/changed artwork, font and historical catalogue; unavailable optional audio, notification and rich-report feature. Core form and parent approval remain usable. |
| C — Real caller and local integration | Actual GDM versus manager UID/GID/filesystem credentials, representative restrictive umasks, valid local PAM include/module variation, harmless formatting and saved-session repair. Ordinary child/admin authentication stays unchanged. |
| D — Lifetime and races | Fresh entry, exit/reentry, ten sequential visits, rapid reentry, healthy reuse, one stale/failed owned instance, interrupted renewal and a competing login. Preserve foreign/live sessions; no endless restart or routine reboot. |
| E — Transient dependencies | Bounded AccountsService/broker/session-bus delay or restart and lock contention, followed by recovery and usable entry. Retain the first cause; test permanent failure separately without claiming a usable request. |
| F — Updates | Unrelated package change and one actual relevant dependency/product update. Confirm fresh/reused session behavior and justified activation without exact old-manager retention. Reuse existing lifecycle histories whose changed inputs warrant them. |
| G — Reachable escapes and policy | Alternate desktop/TTY/SSH routes; exposed links, choosers and service/activation paths; child-writable consumed startup inputs; parent denial/cancellation; account/management authorization; one unavailable-enforcement and one explicit-policy control. Each has a working permitted control. |
| H — Composition and diagnosis | At least three declared combinations across A–F, including original GDM credentials plus optional failure and repeated entry. A real Parent diagnostic download retains the original cause after recovery and reboot without PII. |

R09 selects representative combinations rather than the Cartesian product.
Existing installed cases 267–269 and 290–294 and public kiosk operations are
starting material, not requirements to preserve their internals. Use the
[UI mandate](Mandates/UI-Automation-Mandate.MD), existing semantic operations and
[test ownership map](TestAutomation/README.md); no new coordinate, gesture or
presentation-specific adapter campaign. Safety-negative fixtures may deny their
prohibited operation; those denials neither count as customer entry success nor
excuse rejection of a positive fixture.

Before broad implementation, R02–R04 prove a thin version of the intended route:
passwordless usable form, genuine parent approval, Cancel/exit/reentry, an
unrelated-host change, optional-resource failure, bounded owned renewal, and the
actual alternate-desktop/SSH/launch-route boundary on each platform. Include
manager/service/PAM teardown and Fedora's privileged authentication helper;
no-new-privileges assumptions must not silently disable approval. If this needs
the old host-inventory machinery, revise the design at this gate before extending
implementation.

## Implementation baseline

The previous programme is preserved in Git at
`6978221c2371d9f52945e5cc62da56489463f12c` and in existing runner artifacts.
Completed work remains historical evidence, not acceptance of this redesign:

| Completed old work | Retained value |
| --- | --- |
| 001a/001b/001; 002aa/002ab/002a/002b/002 | Authentication-to-form cause map, generic ambient handling and sanitized admission diagnostics |
| 003a/003; 004a/004 | Installed cases 290/291 on both targets: isolation, deliberate unsafe-input refusal, restoration and public reentry |
| 005a/005; 006a–006h and their 006e prerequisites; 006 | Existing material/view implementation, composition checks and historical bootstrap observations; no obligation to retain that architecture |
| 007a1a/007a1b/007a1c/007a1; 007a2a/007a2b | Canonical history helpers, refusal transport and caller-independent native/Python creation repairs |

The latest [cumulative evidence bundle](../output/test-runs/host/exports/onpc-evidence-bundle-1j5a8l1p/evidence.zip)
contains 6,470 files, SHA-256
`e8042b34cdc19d6e7bbd9b4032c4b77797262661cbc3d63eb0e47d92be2e5fba`.
007a2b recorded 4,120 cumulative host checks, 386 final entry/resource checks,
313 documentation checks and both package builds. These are host/build results,
not corrected installed public-entry acceptance. Case 291's historical final
Fedora/Ubuntu reports are `20261019T094152Z-8236f31a` /
`20261019T094152Z-dee12fa6`. Older qualification remains in the
[design evidence limits](SystemDesign/Kiosk-Confinement.md#verification-scope-and-evidence-limits).

Carry these unresolved facts forward:

- Ubuntu case 293, `20261020T015724Z-9595ee55`, failed before ambient visits:
  authentication/routing succeeded; retained admission refused at
  `source-staging`; no usable form appeared. Original selected-input digest:
  `413c0f1fd6afce29870cfe38a8158d3eefeb36a255bf3bb53b5ea7ac7de7f1c7`.
  Later host creation repairs do not turn that attempt into a pass.
- GDM creates state after changing group credentials; earlier bootstrap probes
  tested the wrong ordering. R02–R04 use corrected actual caller witnesses.
- Separate helper cleanup reported `retained-manager:public-session-remains`.
  `login_state()` included all logind sessions; exact failed IDs were not
  captured. Correlate before changing classification if R09 reuses that helper.
  Outer restoration ended resources but did not prove helper cleanup.

## Scope reconciliation

Old unfinished work is superseded, not completed. Useful obligations move as
follows; obsolete mechanisms do not survive as hidden prerequisites:

| Former scope | Successor |
| --- | --- |
| 007a2c cleanup; 007a2d/007a2e bootstrap | R09 owns a demonstrated reused-helper defect; R02–R04 own actual replacement entrypoint/caller/loaded-policy proof. |
| 007a2/007a3/007a and 0071/0072/007 retained histories | R09–R11 preserve ordinary-host entry, escape protection, recovery and both platforms. Exact manager/view retention and historical “required material changed → refuse” assertions retire where the new contract removes the dependency. |
| 008a/008/009a1/009a/009 authentication | R01/R07 define minimal policy-preserving integration; R09–R11 verify supported variation and explicit denial. No global null-token enablement or ordinary-account bypass. |
| 010a1/010a/010 feedback | R08/R09–R11 preserve original-cause collection and real Parent download after recovery/reboot. |
| 011a/011 reconciliation | R12 maps final inputs, resolves current links and retires obsolete code/tests/docs. No new full-product campaign. |

R01 explicitly maps changed behavioral expectations before tests are edited.
Preserve safety requirements; retire implementation assertions when their
mechanism is replaced. Never change expectations merely to pass. New work must
name a demonstrated failure or direct regression risk, finite deliverable and
acceptance. Do not recreate the old programme as an expanding list of theoretical
hardening prerequisites.

## Execution

Use [Execution plans](Execution-Plans.md), [Approval tools](Approval-Tools.md)
and [failure handling](../tests/README.md#handling-test-failures).
The coordinator remains GPT-6.1 Sol High; bounded delegation follows the shared
model guidance. Preserve mandatory **GPT-6 Astra XHigh review and revision for
each product fix**, and apply it to R01's architecture too. Review actual
reachability, availability consequences and both platforms; resolve actionable
findings and revalidate material revisions. Test counts cannot replace the
public result.

`tools/kiosk-prompt --check` validates the master and briefs without execution.
Only a later explicit execution request starts `tools/kiosk-prompt --tasks 1`
or `--tasks 0`. The wrapper selects this master and its new plan namespace.
Old run `b65c57a9fa994b3ba4f2ab6fe9df6307` stopped safely after 007a2b with
cleanup complete. Its checkpoint and suspended handoffs remain untouched in
existing storage. Do not manually rewrite them or use `--reconcile` to pretend
changed scopes are the old tasks. No second legacy plan remains in the repository.

Briefs own only their listed scope. Use the lowest effective host checks and
`make build` when packaged inputs change. Installed work requires the
[VM mandate](Mandates/VM-Mandate.MD), registered targets, maintained launchers,
public results and owned cleanup. Never install the product on the development
host. New product strings require all supported translations; What's New
synchronization still needs its separate explicit authorization.

Close only when positive availability families and concrete confinement controls
pass on both final candidates, original failures remain diagnosable, no unexplained
rejection remains, owned state is restored and obsolete requirements are removed.
Neither a support exclusion invented after failure nor a diagnostic-only screen
satisfies ordinary kiosk availability.
