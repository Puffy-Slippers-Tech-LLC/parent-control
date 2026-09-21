# Authentication tasks

Apply the [shared contract](README.md). Entry dependencies are in
[01-Entry](01-Entry.md). These tasks are high priority, but successful approval
does not block passwordless kiosk entry or disabled-child case 57.

Use separate MATE and Shell provider bindings in
[accessible_ui.py](../../../tests/e2e/accessible_ui.py); the kiosk's
[MATE service](../../../data/systemd/user/oh-no-parent-control-polkit-agent.service)
is not Shell Polkit. Reuse the existing
[credential boundary](../../../tests/e2e/README.md#credential-staging-and-password-capture-boundary),
UI19 transport and challenge ledger. Challenge metadata is not an approval result.
Expected request details come from the public form and prompt, never broker probes.

| Done | ID / budget | Requires | Bounded deliverable and measurable acceptance |
| --- | --- | --- | --- |
| [ ] | A01 / 50 min | G02 | **Host keyring Cancel:** add only the provider-local cancellation route. Wrong-owner, queued/replacement-dialog, incomplete-absence and uncertain-action tests pass; no secret is accessed and unknown prompts remain refused. |
| [ ] | A01v / 45 min | A01, G06, S01, prepared VM | **VM keyring Cancel:** qualify one real gcr prompt. Correct dialog disappears, the interrupted read resumes without replay and the expected surrounding surface is independently observed. Evidence/cleanup pass; a synthetic absent-prompt mapping cannot qualify this route. |
| [ ] | A02 / 45 min | G05, customer 012a/004 challenge prerequisites | **MATE prompt diagnosis:** enter one real request challenge, record the agent owner, selected administrator, displayed request context and protected-field accessibility; cancel normally and observe the form. Include brief ID/source lookup only if useful. Evidence/cleanup passes; missing public context is an explicit blocker, not inferred from internal state. |
| [ ] | A03 / 55 min | A02 | **Host MATE proof:** implement AUTH01's exact observed route and explicit Cancel. Tests reject wrong administrator/child/request, multiple fields, nonempty or unfocused field, stale challenge and wrong agent. Cancel has independent disappearance/form readback. No password submission in this task. |
| [ ] | A04 / 45 min | A03, customer 013, prepared VM | **VM MATE Cancel:** independently enter a real challenge twice through separate deliberate requests; qualify each and cancel once. Both return to the expected form with choices preserved and no error; evidence/cleanup pass. This qualifies Cancel only. |
| [ ] | A05 / 55 min | A03, customer 004/004a | **Host submission:** connect the existing secret API to two fresh same-challenge MATE proofs and one explicit submit. Add intended/wrong recipient, stale/reused challenge, capture and uncertain-delivery regressions. Preserve rejection and request-result observations as separate operations. |
| [ ] | A06 / 50 min | A05, customer 020 result implementation, prepared VM | **VM approval:** one correct fixture password approves the declared request; observe public success and the specified station exit to GDM. Fresh challenge, capture reconciliation and cleanup pass. Authentication disappearance alone fails. |
| [ ] | A07 / 50 min | A05, customer 020 result implementation, prepared VM | **VM rejection:** one declared wrong fixture password produces explicit rejection, then normal Cancel returns to the expected unchanged form. No timeout-as-denial and no automatic retry. Evidence/capture/cleanup pass. |
| [ ] | A08 / 55 min | A03, A05; customer 048a for live prompt availability | **Host Shell agent:** implement its distinct prompt owner/recipient selectors and reuse the challenge/input guards. Test wrong provider/session, ambiguous field, stale challenge and cancellation/result projections. Do not copy MATE selectors or share its qualification claim. |
| [ ] | A09 / 50 min | A08, customer 048b result implementation, prepared VM | **VM Shell Cancel:** open an overlay request and cancel its real Shell challenge; observe preserved overlay choices, no error and usable form. Include independent valid entry, wrong-recipient refusal and cleanup. |
| [ ] | A10 / 50 min | A08, customer 048b result implementation, prepared VM | **VM Shell approval:** submit once for one declared request; observe request success and the recipe's child return result with capture/cleanup. Full remaining approval/rejection variants stay with customer 048b. |

Customer references here mean the relevant leaves are implemented, not that the
whole task has already passed: 019/020 and 048b consume this qualification work.
Keep the dependency direction explicit when updating those briefs; do not create
a cycle requiring a completed approval task before its adapter can be qualified.

These tasks supply prerequisites to **019–021**, complete customer cases
**50, 51, 52**, and overlay **048b**. Implement each remaining owned request
result/exit in its existing task, then run each whole scenario separately.
Settings Unlock is a separate challenge context under U01; terminal package
authentication is L01, not either graphical agent. Required shared live
regressions remain R07–R11.
