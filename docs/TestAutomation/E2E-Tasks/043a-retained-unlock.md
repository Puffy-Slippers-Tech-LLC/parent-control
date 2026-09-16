# 043a — Qualify retained unlock and return from the lock screen

Budget: 35–55 minutes, including a normal verification cycle; this is not a stop timer.
Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task) and repository approvals.

## Scope and entry

Consumer: E2E-008/retained-unlock (21). Scope: GDM02's retained-child lock entry, DESK08 and DESK11's lock-screen return.

Required implemented capabilities: Intended-child fresh login, DESK05/06/07, repeated UI19 challenges and FLOW02. Resolve them from the
[catalogue](../E2E-Building-Blocks.md#ordered-building-block-catalogue) and
maintained source. Begin a fresh guarded attempt; no previous task document or
VM state supplies context.

## Work

Qualify GDM02(child, destination=lock) for the already observed retained child session. Compose DESK06, two fresh DESK07 proofs, UI19, submission and the declared success/time-denial observation. Bind the normal lock-screen Switch User route separately from rejected GDM; never reuse a GDM secret proof on the lock surface.

## Live VM acceptance

On the VM, enter the child with positive daily time, lock normally and unlock with the intended correct credential. In an independent attempt, prepare positive time in Parent, log Parent out normally and admit the child. Switch User from the child, sign Parent in fresh and change daily time to zero through the UI. Switch to GDM and select that retained child through GDM02; require its lock challenge and explicit time-limit denial after correct authentication. Reach GDM through the observed control. Refuse stale/wrong-recipient proofs and pass credential/cleanup checks before live execution. This configured-zero qualification makes no natural-expiry claim.

Run affected safety/worker checks, then the planned fixed qualification
`tools/run-tests integration check_e2e_expiry`, or the complete named consumer if
runnable. Reuse the master's guarded qualification route. Require every stated
result and owned cleanup on the live VM; diagnostic success earns no scenario
coverage.

## Close out

After successful cleanup, update the callable, qualified scope and remaining
work in [the catalogue](../E2E-Building-Blocks.md), then check this task in the
[master](../E2E-Execution-Plan.md). If the complete E2E consumer also passed, run
`tools/generate_test_coverage.sh` (the launcher for
`tools/generate_test_coverage.py`) before checking it off. Delete this task when
no longer needed, replacing its master link with plain text. No new evidence or
history document. Follow the master's Markdown checks.
