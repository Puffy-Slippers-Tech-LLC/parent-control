This is a separate progress review using gpt-6-astra / xhigh, Standard.
Do not implement a slice, run tests/VM operations or launch another session.

Read the two supplied summaries, docs/TestAutomation/Continuation.md and the
selected task's active handoff before judging. Use their cumulative customer
progress record and frozen finish line, not only the difference between two
small slices. Do not read the operator summary file, source, logs, transcripts
or evidence archives. With insufficient cumulative data, state the uncertainty;
do not assume an expanding task is healthy.

Scope comes from the 2026-09-14 operator direction and E2E-Coverage.md:
- Customer E2E operates/observes as real users across all app surfaces. The
  timeout/login example is not a special priority. Backend product probes,
  internal fault injection and the deferred policy design are outside scope.
- Preserve existing completed unit/component/system and safety tests.
- Mechanical installation/upgrade/removal in Tasks 18/20 retains internal
  checks and cumulative recovery checkpoints, after the customer queue.

Judge completed customer variants, executed progress toward frozen remaining
steps, actual blockers and growth/shrinkage of the remaining work. Passing
unit/helper tests, new probes, scope transfers, smaller denominators and revised
plans are not completed customer scenarios. Mechanical work is judged against
its finite installation milestones and remaining defects.

After two customer implementation slices without a completed variant, require
a course correction before another prerequisite slice. Carry the counter across
tasks/chats/model changes; reset only on a complete customer pass. A necessary
first adapter can be finite progress, but an indefinitely expanding chain cannot.

Return one of:
- healthy: complete customer outcomes and a shrinking credible finish line, or
  a first finite adapter tied to a named consumer. Mechanical milestones may
  establish progress under their own scope. Do not edit handoffs.
- intervene: a different concrete route can complete a customer variant in the
  next slice, or independent ready customer work can proceed. For mechanical
  work require its named milestone. Revise both handoffs as below.
- blocked: required approval/access/product repair or another outside decision
  prevents all independent authorized work, an explicit recovery checkpoint
  requires a decision, or no defensible new intervention exists. Preserve the
  exact blocker; never route around denial or reactivate deferred engineering.

For intervene, use apply_patch on both Continuation.md and the relevant
Task-<ID>.md. Preserve evidence, actual failures, counters, scope, ownership,
permissions and mechanical recovery ledgers. Replace the next action with a
different concrete approach, exact complete-variant acceptance signal and stop
condition. Do not add internal assertions, another probe qualification or new
framework as the breakthrough. Check local Markdown links and scoped whitespace;
do not read/diff the operator log or edit product/tests/launcher/portal files.

If the preceding intervention failed, do not renew it automatically. Record the
case/dependency blocked and select a genuinely independent ready customer case,
or return blocked when no authorized independent work remains. Missing internal
proof alone does not block a visible customer result; an actual customer failure
must not be relabeled passed.

Choose gpt-6-astra / xhigh or max for an intervention slice only, with a concrete
reason. Keep ordinary reassessed Settings in Continuation.md; the supervisor
consumes the override separately. Stronger settings do not guarantee completion.

Return only the supplied structured verdict; do not add schema fields:
- decision: healthy, intervene or blocked.
- evaluation: one or two sentences about customer completions, remaining scope
  and whether intervention is needed; mechanical work names its milestone.
- effort: xhigh or max for intervene; none otherwise.
- breakthrough: exact complete customer variant/result or mechanical milestone
  required next slice for intervene; empty otherwise.
- task_document: revised docs/TestAutomation/Task-<ID>.md for intervene; empty
  otherwise. Both task and continuation must actually be saved.

End the session. The supervisor reviews before another implementation slice.
Reviews do not append summary sections.
