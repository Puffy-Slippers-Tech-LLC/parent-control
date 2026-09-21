# Files, choosers and document tasks

Apply the [shared contract](README.md). Schedule these when their first customer
consumer is eligible, after the urgent entry/authentication work. The provider
route may use easy public IDs and scoped semantics together. Portal and native
dialogs are different routes; a pass in one never qualifies the other.

Work in the provider operations and sanitized projections of
[accessible_ui.py](../../../tests/e2e/accessible_ui.py) and
[ui_observations.py](../../../tests/e2e/ui_observations.py), then the existing
customer task's journey/worker. Use prepared synthetic fixtures only. Normal
Location navigation, selection, copy, rename, Save and Open are customer input;
direct filesystem edits are not acceptance. Shared host refusal checks and live
evidence/cleanup apply to every row below.

| Done | ID / budget | Requires | Bounded deliverable and measurable acceptance |
| --- | --- | --- | --- |
| [ ] | F01 / 50 min | R02; customer 036 synthetic fixtures | **Host Nautilus navigation:** implement one directory's Location navigation and exact fixture-entry projection. Resolve dynamic rows within the provider-owned Files surface. Tests reject another directory, ambiguous names, lost focus and incomplete entry lists. |
| [ ] | F01v / 40 min | F01, prepared VM | **VM Nautilus:** navigate to the declared directory, read its exact entries, refuse wrong entry and collect evidence/cleanup. The public Location and listing must agree. |
| [ ] | F02 / 45 min | F01v | **Nautilus copy:** one declared source is selected, copied to a declared destination through normal input and independently observed there. Wrong source/destination and duplicate-name checks pass. No overwrite branch in this slice. |
| [ ] | F03 / 45 min | F01v | **Nautilus rename:** rename one synthetic file through the public dialog; verify new entry and old-name absence within a complete recognized directory. Wrong-file and cancellation guards pass. |
| [ ] | F04 / 50 min | F01v; customer 037 native caller input | **Host native chooser:** implement one actual caller-owned open/cancel route and exact multi-selection readback. Tests reject wrong dialog/owner, partial selection and uncertain input. Unsupported caller/toolkit remains pending. |
| [ ] | F04v / 45 min | F04, prepared VM | **VM native open/cancel:** select two declared files, verify the exact selected set and caller result; a separate deliberate Cancel leaves the caller unchanged. Evidence/cleanup pass. |
| [ ] | F05 / 50 min | F01v; customer 037 portal caller input | **Host portal chooser:** implement the actual portal/Nautilus route. Use easy Builder IDs within the proven owner/dialog scope and semantics for dynamic files. Caller ambiguity, lost selection and wrong-dialog tests pass. |
| [ ] | F05v / 45 min | F05, prepared VM | **VM portal open/cancel:** qualify the same two-file and cancellation outcomes as F04v through the actual portal route, including the invoking caller relationship and cleanup. |
| [ ] | F06 / 50 min | F04v; customer 037a save caller | **Native save:** save one declared file to a synthetic directory/name, then observe the saved file through Files and the caller's result. Cancel leaves no new result. Unknown overwrite dialogs refuse; overwrite support is not added here. |
| [ ] | F07 / 50 min | F05v; customer 037a save caller | **Portal save:** qualify the same explicit save/cancel outcomes through the real portal route, with fresh dialog ownership and exact filename readback. Native evidence cannot satisfy this row. |
| [ ] | F08 / 50 min | F01v; customer 195 input leaves | **Host document open:** bind the actual text editor's synthetic document identity/content and close/return. Wrong-document, ambiguous-window and uncertain-close tests pass. Reuse R05 code only for the same provider. |
| [ ] | F08v / 40 min | F08, prepared VM | **VM document open:** open the declared file from Files, read expected public content and document identity, refuse wrong document, close/return and collect evidence/cleanup. |
| [ ] | F09 / 55 min | F08v; customer 196 input leaves | **Document edit/save:** type one declared replacement, save normally, observe public clean/saved state, close/reopen and verify content. Wrong-document and uncertain-save checks pass. Missing public saved-state evidence blocks this binding, not just its ID lookup. |
| [ ] | F10 / 50 min | F01v; customer 195/045 archive fixture | **Host File Roller:** bind one archive and entry, its actual content handler and close/return. Wrong archive/entry and uncertain input tests pass. No extraction without a named consumer. |
| [ ] | F10v / 40 min | F10, prepared VM | **VM File Roller:** open the declared archive/entry, verify identifying public content, close/return and collect evidence/cleanup. |
| [ ] | F11 / 50 min | F01v; customer 045 requires PDF review | **Papers or actual PDF handler:** qualify the selected handler with one declared saved document, meaningful public identity/content and close/return. No PDF consumer means defer this row; a window title alone cannot pass it. |

The first provider implementations have separate host and VM rows. Small
extensions such as copy/rename/save include one narrow installed operation.
If an extension will not fit its budget, split it before starting and preserve
both acceptance sets. Do not spend the hour chasing external IDs. Customer
dependencies here mean the specified fixtures/input leaves are available, not
that a whole task consuming this adapter must already be complete.

Return to existing customer **038/039/045/046** for attachment controls, immutable
attachment behavior and diagnostics contents. Their repository-owned rows and
rich editor need real IDs. Run complete cases **152, 154 and 155** only when each
recipe's remaining owned capabilities are implemented; **153** separately owns
validation. Each full-case run is a separate at-most-one-hour task in its existing
brief, with coverage refresh and cleanup. Do not count F01–F11 as those passes.
Later retained-work consumers reuse the actual saved document; they must not
recreate a new window to imitate retained work.
