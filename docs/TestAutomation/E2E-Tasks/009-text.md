# 009 — Replace a nonsecret field value

Budget: 25–45 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-031/validation (153). Scope: UI16.

Required implemented capabilities: FEED01 and FEED03 entry/readback, plus existing focus/input primitives. Use maintained callables and an independent public entry state, never an earlier task document or attempt.

Contract: the named [catalogue rows](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and consumer recipe. Qualify only the bindings named here.

## Work

Implement focus → Ctrl-A → one typed value, or Backspace for empty → exact readback. Register the feedback body/reply projections needed by the consumer; preserve masked-field refusal and declared input pace.

## Live VM acceptance

On installed Parent feedback, replace a synthetic value, replace it again and clear it; independently read each exact value, including zero length. Wrong or disabled targets refuse before input.

Run affected safety/worker checks, then planned fixed qualification `tools/run-tests integration check_e2e_feedback_local`, or the full named consumer if runnable. Reuse/create the fixed entry under the master's qualification contract. Every result above and owned cleanup must pass on the live VM; diagnostic success earns no scenario coverage.

## Close out

After successful cleanup, check this task in the [master](../E2E-Execution-Plan.md) and update [catalogue/scenario status](../E2E-Building-Blocks.md) using its readiness rules. Delete this task when no longer needed, replacing its master link with plain text. No new evidence/history document.
