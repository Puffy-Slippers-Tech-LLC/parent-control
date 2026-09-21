# External UI adapter execution plan

This plan breaks external-provider work into tasks budgeted for **one hour or
less**, including the selected checks and close-out. It supports the existing
[customer queue](../E2E-Task-Queue.md); it does not replace its scenarios,
expected behavior or readiness records. All tasks start unchecked. Writing this
plan establishes no implementation or installed qualification.

Start at [System design](../../System-Design.md), use the
[approval contract](../../Approval-Tools.md), and follow the
[UI automation mandate](../../../AGENTS.md#ui-automation-mandate).

## External IDs are optional

External IDs are **nice to have, not must-have or hard-earned**. Spend at most
**10 minutes per provider surface, once**, checking an available accessibility
tree and, if useful, a few official documentation/source pages. Reuse earlier
findings; do not repeat this allowance in each task. Use readily usable IDs,
including partial IDs inside an otherwise qualified provider adapter.

If IDs are not readily available, proceed immediately with the approved
provider-specific workaround: scoped public accessibility semantics and
ordinary keyboard navigation with observed focus and results. No upstream
patch, provider rebuild, reverse-engineering project or complete-ID hunt is a
prerequisite. Do not invent IDs from labels or describe semantic selectors as
provider-owned IDs. No renewed approval is needed for the existing exception.

Geometry/image techniques are permitted only inside that explicit adapter when
accessibility actions and keyboard navigation cannot work reliably. Record the
concrete reason and qualify that route separately. Ownership, ambiguity
rejection, secret-recipient proof and single-use/uncertain-input guards still
apply. An unavailable safety proof is a blocker; an unavailable external ID is
not. Repository-owned apps, child extension and fixtures still require IDs.

## Current task

The next task is **O02** in [Entry and session controls](01-Entry.md). A session
may therefore start with only: `Execute the next task in
docs/TestAutomation/External/README.md`.

O01's diagnostic run `20260921T165540Z-4f446a7c`
passed guarded station entry and owned window/form readback. Its captured stream
showed a complete public tree with one application, window, form and every
required control ID; no incomplete reads or query errors occurred. The observer
spent 24.8 seconds and 113 traversals checking prompts, then repeatedly traversed
the desktop/application/window for individual controls. Its 90-second work bound
stopped the `kiosk-duration-custom` lookup at 157 traversals and 6,551 node visits.
This diagnoses redundant observer work; it does not establish a product defect.
The full qualification failed and its collection stage did not run. Diagnostic
measurements remain recorded here; the transient report/log has expired under
runner retention. Cleanup passed, the lease completed and the pinned VM was
confirmed off.

O02 should reuse a fresh complete scoped observation within each read, preserving
application/surface ownership, duplicate rejection, stale/incomplete-read refusal
and all form assertions. Add regression coverage for traversal cost as well as
correctness before G05's installed qualification. Do not raise timeouts, reuse
stale snapshots across observations, or add selector fallbacks. The diagnostic,
greeter startup wait and viewer changes are test-only and activate on invocation;
no product rebuild is needed for those changes. Both the guest screen and
sanitized SSH observation progress use the existing `tools/watchvm` channels.

Treat this pointer as part of every task's close-out. After completing a task,
mark its row complete, append its short result or artifact pointer, and update
this section to the next task. First honor any customer task released by that
row and the customer queue's lowest-eligible-case rule. Otherwise choose the
first unchecked external row whose listed prerequisites are complete, using the
file order below and then table order. Do not skip an eligible task merely
because a later task is more convenient.

If the current task is incomplete, keep its row unchecked and append its blocker
and exact return condition. Keep this pointer on that task while the return
condition can be pursued; when it cannot, point to the first independent eligible
task and leave the blocked row unchecked. At the start of a session, verify the
pointer against the task tables and repair a stale pointer before doing task work.
When no task is eligible, point to the earliest blocked task and its return
condition instead of claiming completion.

## Order and task size

1. [Entry and session controls](01-Entry.md): unblock task 011's passwordless
   station entry and independently qualify the owned request form.
2. [Authentication](02-Authentication.md): prioritize the actual kiosk MATE
   agent, then the Shell agent. Full approval is not a prerequisite for 011 or
   disabled-child case 57. Session and authentication host work may progress
   independently once its listed prerequisites exist.
3. [Retained regressions](03-Regressions.md): restore Shell search, terminal and
   license-viewer routes needed by mandatory existing cases. Run an eligible
   regression as soon as its own dependencies pass; do not wait for all providers.
4. [Files and feedback](04-Files.md): follow the first eligible attachment,
   diagnostic-export and retained-document consumers.
5. [Remaining customer dependencies](05-Remaining.md): package authentication,
   lock/retention/lifecycle, desktop launch and Settings, when their customer
   tasks become eligible.

Each table row is one task. Dependencies are task IDs; `customer NNN` means the
existing queue capability, not a previous scenario execution. The customer
queue's lowest-eligible-case rule still applies between capability tasks.
Read the chosen row, this shared contract and its named source only.

Budgets assume listed prerequisites are complete. P02 owns initial preparation;
missing setup or a required rebuild is separate prerequisite work, not hidden
inside an adapter task. Before starting, split any task expected to exceed
60 minutes into implementation and one-route qualification rows with explicit
acceptance. During work reserve the last 10 minutes for verification/close-out;
do not start another attempt that cannot fit. Never cut short an owned live
attempt or bypass cleanup to meet the estimate. An overrun or failed check leaves
the task incomplete with a concrete continuation; time spent is not acceptance.

Use existing functions, fixed operations, evidence and runner envelopes. Add
only the small provider helper needed by the named consumer. No plugin system,
generic selector language, compatibility framework, new runner or parallel VM
controller. Keep the standalone guest transfer intact. Prefer Sol for settled
edits and Astra for unresolved ownership, credential safety or diagnosis, as
required by AGENTS.md.

## Evidence and assumptions

The [provider catalogue](../E2E-Building-Blocks.md#external-provider-qualification)
records no route qualified under the updated exception. Recorded inspection of
Shell 50.1 found no nonempty IDs. A `None` entry in
[accessible_ui.py](../../../tests/e2e/accessible_ui.py) means an incomplete
mapping, not proof that a provider can never expose an ID. Settings and the
portal chooser have partial Builder IDs; those observations do not qualify input.

The kiosk uses [MATE Polkit](../../../data/systemd/user/oh-no-parent-control-polkit-agent.service),
which is missing from the current registry. Shell Polkit is explicitly refused.
The shared prompt middleware preflights both Shell Polkit and keyring mappings
on non-GDM operations, including station observation. These are implementation
gaps, not new product requirements.

[Task 011](../E2E-Tasks/011-kiosk-entry.md) records a prior installed observer
seeing only the desktop root. Its cause remains unverified. Host owned-ID tests
do not qualify the installed kiosk bus. UI15 session-choice handling, actual
terminal/viewer handlers and public saved-document state also need investigation.

| Provider / scope | Current gap | First consumers / task group |
| --- | --- | --- |
| GDM | Complete mapping absent; guarded consumers exist | GDM01–09, REQUEST01; G tasks in Entry |
| Shell desktop/session menu | Observed ID absence; retained consumers need migration | DESK01–04; S tasks in Entry |
| MATE Polkit / Shell Polkit | Missing MATE binding; Shell refusal; AUTH consumers pending | AUTH01/02/04, tasks 019–021 and 048b; A tasks |
| gcr keyring | Mapping absent; Cancel mechanics retained | Desktop prompt handling; A01 |
| Shell search / window switch | Mappings unqualified; consumers partly retained | SEARCH01–06, DESK10, cases 3–6/151/193; R tasks |
| Terminal / default license viewer | Handler/mapping qualification missing; help/denial/license consumers retained | FILE01/02/06, INFO02, ABOUT02/03; R tasks |
| Native chooser / portal chooser | Native mapping absent; portal IDs partial; consumers missing | FILE03, FEED06/08; F tasks |
| Nautilus / Text Editor / File Roller / Papers | Mappings and consumer operations missing or unqualified | FILE04/05/07/08/09, attachments/export/retained work; F tasks |
| Shell lock/network/reboot/suspend/notifications | Each surface unqualified; several consumers missing | DESK05–12, LIFE02/03/06; L tasks |
| DING desktop icons | Source registry gap; catalogue needs its own row | Declared desktop-launch route; L09 |
| Settings Users / Date & Time | Partial Users IDs; page/wizard consumers pending | ACCOUNT01/02, TIME05; U tasks |
| Browser / mail handler | Actual handlers and required operations not inventoried | INFO01, customer 185p/185o; U06 |
| Graphical VT6 getty/login | Retired routes refuse; safe graphical proof unqualified | Only a named remaining harness consumer; U07 |
| Owned kiosk, Parent, child extension, WebKit editor and app fixtures | Separate installed ID/consumer qualification | O tasks and existing customer tasks; never the external exception |

Support initially means the exact **Ubuntu 26.04 pinned VM package versions,
UI locale and keyboard layout actually qualified**, not every GNOME 50 release
or later Ubuntu. Record this small tuple in normal qualification evidence and
the relevant catalogue scope. The observer's `LANG=C.UTF-8` does not set the
provider's locale. Keep necessary localized strings inside the adapter; an
unknown version/locale needs a bounded qualification task, not speculative
support or silent fallback. Do not build a translation/version matrix now.

## Shared acceptance and close-out

- **Host tasks:** pass focused tests for wrong owner/session/surface, ambiguous
  targets, stale handles, hidden/disabled input, focus loss, incomplete reads and
  uncertain-input refusal. A positive input must have independent result checks.
  Keep owned-ID and retired generic-selector refusal tests intact.
- **VM tasks:** exercise the declared real input/result, independent valid entry
  and wrong-entry refusal, collect sanitized evidence and pass owned cleanup.
  Reacquire after transitions. Incomplete trees never prove absence. Provider
  metadata may bind the UI connection; backend state never supplies customer
  acceptance. Secret tasks additionally require two fresh same-challenge proofs,
  intended/wrong recipient, empty masked focused field, sealed capture and
  single-use delivery without replay.
- Before any live run, pass applicable cleanup-safety tests in isolation. Reuse
  `tools/run-tests --help` and `--list`, then selected `unit` or `ui` files with
  explicit UI timeout. Do not broaden to `host`/`all` for convenience. Stop VM
  maintenance before integration/E2E. Use only the pinned guarded runner.
- Prefer the complete runnable consumer. Otherwise reuse a fixed qualification
  in the existing envelope. A new argument-free `check_e2e_...` must exist, have
  cleanup coverage and be registered through the existing route before use.
  Existing selectors are `check_e2e_kiosk_entry` and
  `check_e2e_desktop_session`; other names in future work are not assumed to exist.
- A checked host or diagnosis task records only its stated deliverable. Mark a
  provider route qualified only after its VM input/readback, evidence and cleanup
  pass. Shared GDM/secret/routing changes also retain the required live regression
  gate, cases 1, 3, 4, 5 and 151; track it in R07–R11 without pretending a host
  task ran those cases. Until that gate passes, keep overall migration close-out
  pending. Do not turn a failed complete journey into a passing slice.
- Complete customer tasks and scenario registrations stay in the existing queue
  and `scenarios.json`. After each passing complete case, regenerate coverage
  with `tools/generate_test_coverage.sh`. Update only the exact catalogue scope
  proven, after cleanup. Preserve retained ready bindings and frozen customer
  scope; implementation registration alone is not installed acceptance.
- Append only a short result/artifact pointer or blocker/return condition to the
  task row. Use existing artifacts, not new evidence histories. Validate changed
  Markdown with `tools/read-only links`. Test-only changes activate on invocation;
  a necessary product fix gets its own package-activation classification.

The completed G04 slice binds only the observed passwordless
`default-request-form` station branch and its independent readback after one
fresh station-focus proof. **O01** is complete as diagnosis only. **O02** is the
first eligible unchecked row, with the demonstrated traversal defect above.
G05 and provider/customer readiness remain pending.
