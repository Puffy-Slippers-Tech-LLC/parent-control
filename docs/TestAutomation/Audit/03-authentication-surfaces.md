# 03 — Contain and migrate authentication identity paths

**Recommended model: GPT-6 Astra. Effort: high.** Recipient identity, secret
delivery and uncertain-input handling are security-sensitive correctness work.

**Prerequisite:** [02 inventory](02-owned-ui-and-inventory.md) and
[shared preflight](README.md). **Status:** Not started.
**Next:** [04](04-desktop-and-external-apps.md).

## Scope and work

In [accessible_ui.py](../../../tests/e2e/accessible_ui.py), trace `greeter_list`,
`greeter_navigation`, `greeter_prompt`, `password_recipient`, authentication
operations in `run`, `system_prompt_control`, `system_prompt_absent`,
`handle_system_prompt`, and their helpers/callers. Include prompt middleware
that can run during unrelated waits. Review
[fixture credentials](../../../tests/e2e/fixture_credentials.py) and the
[provider contracts](../E2E-Building-Blocks.md#functional-validation).

1. Require public, provider-owned application/surface/recipient/control IDs before
   any discovery, input or readiness decision that previously used labels, roles,
   structure or pointer geometry. Names/states may then verify the selected
   recipient and sole focused, enabled, showing, empty masked field.
2. When the external provider lacks its required IDs, return a bounded, explicit
   blocker before input or secret API use. Do not inspect a live greeter, switch
   accounts, open real authentication prompts or use a VM in this task. Catalogue
   keys remain requirements until an actual supported provider mapping exists.
3. Preserve wrong-recipient refusal, two fresh proofs where required, capture
   sealing, one secret delivery, no replay after uncertain delivery, and normal
   rejection/cancel/disappearance assertions. Keep serial authentication's
   separate transport proof and existing behavior intact.
4. Remove reliance on keyring Cancel text/role and pointer-based cancellation.
   Unknown or unqualified prompts block the consumer; absence must refer to the
   qualified surface, not a text search or silence. Coordinate payload consumers
   belong to task 05; record their disposition so that task cannot revive them.

## Verification and completion

Run affected authentication/credential/adapter unit files through
`tools/run-unit-tests` with literal quoted paths discovered from the inventory.
Include `tests/unit/test_accessible_e2e_ui.py` and
`tests/unit/test_e2e_fixture_credentials_cleanup_safety.py`.
Use fake public-ID trees to verify missing/duplicate/wrong-owner/wrong-recipient
refusal and that blocked paths send neither keys, clicks nor secrets. Preserve
behavioral assertions on the ID-capable test path; add refusal checks separately.
Do not change an installed behavior expectation into an expected failure.

Finish with either an ID-only implementation awaiting installed qualification,
or safe containment and an exact provider blocker. Update task 02's inventory
and the existing provider catalogue with missing contracts, affected consumers
and return checks. Unit doubles establish safety behavior, not live GDM/Polkit/
keyring qualification. If assertion migration exposes a product mismatch, follow
the shared regression procedure rather than accepting it here.
