# 034a — Qualify remaining feedback formatting operations

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Read only this context

Read the UI24 and FEED04 catalogue rows, the
[case 152 finite formatting data](../E2E-Scenario-Recipes.md#feedback-local-values),
and the [composition preflight](../E2E-Building-Blocks.md#composition-preflight).
Apply the UI automation mandate and capability acceptance contract through the
master's scoped reading routes.

Start at `tests/e2e/format_qualification.py`,
`tests/integration/graphical_smoke/lib/onpc_format.pm::apply_bold`, and
`tests/e2e/accessible_ui.py::format_operation`, `formatting_attributes`,
`rejection_formatting` and `feedback_plain_text`. For block formats, reuse
`onpc_format::apply_block`, `AccessibleUI.block_operation` / `block_semantics`,
`tests/e2e/block_semantics.py::read_blocks` and its finite `BODY`/`RANGES` binding.
`tests/e2e/feedback_block_semantics.py::BlockSemanticsJourney` and
`tests/unit/test_e2e_feedback_read.py` cover the qualified independent envelope.
Follow the existing format
dispatch, observations and `tests/unit/test_accessible_e2e_ui.py` checks.
The current weight-only reader and four-style rejection reader do not implement
the remaining recipe operations. Inspect public editor identities and APIs as
needed; no DOM, private draft, toolbar-only or screenshot-only proof.

## Scope and prerequisites

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **033** — UI24/FEED04 bold-range input and public attribute observation.
- **034aa** — Customer-facing block semantics and shared public text association.

## Session boundary

Task 034aa has delivered and qualified the editor accessibility capability.
Reuse its heading/list/quote/code operations and bounded reader; this task retains link,
remove-formatting and the complete finite all-format composition. No format
assertion or guard is removed, and case 152 remains separate.

## Implementation and expected results

Extend the shared format operation and observation binding for the remaining
heading, numbered/bulleted list, quote, code block, link and remove-formatting
results. Bind explicit bounded synthetic text/ranges and expected public
attributes before implementation. Preserve existing bold, italic, underline
and strike checks; reuse their qualified mechanics where applicable.

Use ordinary editor selection and offered controls, independently read actual
public inline range attributes and block semantic structure associated with the
exact text ranges, and compare removal with unformatted text. The block route
is qualified for 034aa's distinct `body-blocks` lines, including heading levels 1/2;
extend the shared finite binding for this task's recipe without copying its mechanics.
Qualify independent valid entry, close/reopen observation and wrong-entry
refusal without restorative input. If a required result has no supported public
observation, preserve that blocker instead of weakening the assertion.

Keep inputs, transport and comparisons in shared helpers; the qualification
worker and later case must call the same sequence. No Send. Do not register or
complete case 152, attach its file, or absorb its full draft lifecycle history.
First scheduled consumer: [E2E-031, case 152](034-case-152.md).

## Observation decision and qualified prerequisite

The required Text range proof is not supplied by WebKit's AT-SPI
`GetAttributeRun` implementation for heading, list kind, quote or code-block
semantics. Its [public Text implementation](https://github.com/WebKit/WebKit/blob/main/Source/WebCore/accessibility/atspi/AccessibilityObjectTextAtspi.cpp)
returns font/style/decoration, visibility/editability, direction/indent,
justification, invalidity and language attributes. It does not return semantic
block-format attributes. Font size, family, indentation or toolbar state cannot
substitute for the required semantic result.

The application publishes formatting-control IDs in
`common/oh_no_parent_control_ui/rich_text_editor.py`, including generated heading
options and link controls. Those identify inputs. The editor now also exposes
content-derived heading/level, list-kind, quote and code semantics. The
`AccessibleUI.formatting_attributes` and `rejection_formatting` readers prove
only their documented inline attributes.

The developer authorized targeted accessibility enhancement after public
meaning/text inspection established the platform route. Task 034aa's product
implementation and shared reader passed installed qualification in
`output/test-runs/host/reports/20260927T220402Z-60e41f1b/report.md`.
For code, the role-bearing object can contain a text-bearing descendant rather
than implementing Text itself. The temporary prototype is removed; normal
product-preview regressions cover removal, undo/redo and delta restoration.

Public semantic object attributes and exact text-range association are authorized
as complementary block proof for the qualified scope.
Inline attributes, independent text equality, ambiguous/incomplete-tree refusal,
owner/ID guards, independent entry and wrong-entry refusal remain mandatory.
Neither DOM/private-state reads, toolbar-only proof nor cosmetic comparisons are
permitted. A result node's role is observation after resolving the editor by ID;
it is not a replacement input selector.

No `check_e2e_feedback_formats` selector has been implemented or invoked, and
no live VM attempt or complete host validation of this capability occurred.

## Live VM acceptance

Implement the planned argument-free selector
`check_e2e_feedback_formats` before invoking it. Complete affected host and
cleanup-safety checks through `tools/run-tests`, then prepare the app snapshot
and open the maintained viewer under the live contract. Execute:

```sh
tools/run-tests integration check_e2e_feedback_formats
```

Require every new public result, independent entry/refusal, collection, owned
cleanup and baseline restoration. Requalify the existing `check_e2e_format`
binding and `check_e2e_feedback_rejection` if its shared readers/actions change;
verify the latter selector in the maintained inventory before invocation.
Follow the session's first-live-failure boundary: preserve evidence and return
without repairs or retry after a new live failure.

## Close out

Maintain precise UI24/FEED04 qualified scope in the catalogue. Follow the
[completion contract](../E2E-Execution-Contracts.md#completion-and-document-cleanup),
check only 034a after acceptance and cleanup, remove this brief, and return the
pointer to 034. Leave case 152 implementation and acceptance to its own session.
