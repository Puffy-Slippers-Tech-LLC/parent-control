# 307b — Qualify inherited Parent dialog language and drafts

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **009** — Public synthetic body/reply editing and independent readback.
- **030** — Parent feedback draft preservation and normal dialog closure.
- **185p** — Parent About entry and public information reads.
- **300g** — Parent language selection.
- **307a** — Permitted installed Hebrew presentation observations.

Estimate: 20–30 minutes.

## Scope and acceptance

Qualify Parent's shared About/feedback binding in English and Hebrew. Task 307a
qualified only the Parent language chooser's logical text and keyboard/focus
binding; its `AccessibleUI.language_presentation` reader is chooser-scoped.
Reuse that contract and extend the existing dialog readers for their own public
IDs and ownership. Shared IDs do not transfer chooser qualification to dialogs.
Observe inherited translated controls and
Hebrew/restored English logical text on both dialogs under the mandate's
no-visual acceptance rule, unchanged product/application names, and the exact
synthetic body `שלום Alex 75` and reply `rtl-check@example.invalid`.
Close only the dialog, change language through public Preferences, reopen and
independently compare the retained draft/reply before any new input. Preserve
focus according to each explicit public input/result boundary and verify
keyboard use in both directions. No Send or external-link navigation.

Use only a normal customer route that actually preserves the same draft; do not
set a translation context or draft privately. A modal/public-entry limitation
is a retained gate, not permission to substitute a host fixture. Refuse
wrong-surface, stale/ambiguous ownership and altered synthetic values.

## Shared implementation

Extend shared `open_about`, `open_feedback`, `feedback_snapshot` and
synthetic text profiles in [accessible_ui.py](../../../tests/e2e/accessible_ui.py).
Current feedback readers contain English expectations and Parent-only entry.
Reuse their operations and recorder/worker contracts; qualify translated reads
without changing feedback delivery or the portal.

## Implementation entry

Registered selector: `check_e2e_parent_dialog_language`; fixed installed qualification
previously passed on Ubuntu 26.04, but its report has rotated and must be replaced.
Required Privacy regression remains incomplete.
The fixed `ParentDialogLanguageJourney` / `DIALOG_PLAN` in
[`parent_language.py`](../../../tests/e2e/parent_language.py) uses
`AccessibleUI.parent_dialog_presentation` / `parent_dialog_operation`,
the `synthetic-rtl` profile and `onpc_parent::qualify_dialog_language`.
Each language has two independent entries per dialog, translated public logical
Text/labels, forward/backward Tab focus, owned closure and wrong-entry refusal.
The Hebrew feedback action box uses Shift+Tab from Close to Send and Tab back;
English feedback and the vertical About links use Tab then Shift+Tab.
The exact draft is seeded once and independently compared before input on every
reopen. Host previews use the actual `onpc_text::replace_text` and
`onpc_parent::dialog_navigation` blocks through `gui_blocks.run_block`.

Run the fixed qualification, then the affected regressions on the selected VM:

```bash
tools/run-tests --vm onpc-Ubuntu26.04 integration check_e2e_parent_dialog_language
tools/run-tests --vm onpc-Ubuntu26.04 integration check_e2e_read_parent_information_links
tools/run-tests --vm onpc-Ubuntu26.04 integration check_e2e_feedback_read
tools/run-tests --vm onpc-Ubuntu26.04 integration check_e2e_text
tools/run-tests --vm onpc-Ubuntu26.04 integration check_e2e_feedback_privacy
```

No valid submission is authorized. Registration supplies no live pass or
complete-case credit. This task changes test/tool code only; its files are outside
`PACKAGE_SOURCE_FILES` and build dependencies, so no package build is required.

## Current continuation

The snapshot failure was a proven mechanical input-binding defect: the four
affected regressions selected an older immutable package bundle, while the
current app snapshot was `onpc-v1.3`. Their entries and automatic preparation
now both use `named_input(package_source=True)`, preserving existing inputs.
The maintained builder prepared missing current inputs automatically.
Host validation passed 873 launcher checks, 484 language safety checks, 27
scheduling checks and source checks; earlier real GTK dialog history passed.

Required regressions passed with collection, worker shutdown, owned cleanup,
baseline restoration and preservation:
- [Parent information links](../../../output/test-runs/host/exports/onpc-artifact-export-o_cn_a27/report.md),
  `20261005T182127Z-060b67e7`.
- [Feedback read](../../../output/test-runs/host/exports/onpc-artifact-export-le296ty4/report.md),
  `20261005T182410Z-ffae3fc4`.
- [Text replacement and clearing](../../../output/test-runs/host/exports/onpc-artifact-export-3em2rz8e/report.md),
  `20261005T182625Z-db844a25`.

The final required `check_e2e_feedback_privacy` regression failed after
`parent-selected`, before a first feedback result was recorded, in
`20261005T182934Z-03834083`:
[retained failure report](../../../output/test-runs/host/reports/20261005T182934Z-03834083/report.md).
The recorded category is `e2e:worker-execution-failed`; collection did not run.
Owned cleanup and baseline restoration passed, lease phase is `complete`, and
finalization/preservation passed. No diagnosis, correction or retry of this new
failure was performed. It is not an established product defect.

The earlier fixed qualification report (`20261005T180524Z-988b6b9d`) and its
export have rotated. After repairing the Privacy failure and passing affected
host checks, repeat the fixed qualification and Privacy regression. Preserve the
three valid regression results above while their behavior remains unchanged.
Keep required evidence in the execution/export journals' three-run windows;
each export also rotates its journal. Stop again at a new live failure. Keep
307b unchecked and the pointer here until all acceptance evidence and cleanup
are retained and passing.
