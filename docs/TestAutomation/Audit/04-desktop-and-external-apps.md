# 04 — Migrate desktop and external application consumers

**Recommended model: GPT-6 Astra. Effort: high.** Multiple external providers and
retained absence/readiness paths need a consistent identity boundary.

**Prerequisite:** [02 inventory](02-owned-ui-and-inventory.md),
[03](03-authentication-surfaces.md) shared adapter edits settled, and
[shared preflight](README.md). **Status:** Not started.
**Next:** [05](05-legacy-input-routes.md).

## Scope and work

Review [accessible_ui.py](../../../tests/e2e/accessible_ui.py): desktop/session
methods, `launchable_result`, all search methods, terminal focus/input/output,
command-help observations, `license_content`, document-close/return methods,
and associated operations in `run`. Trace consumers identified by task 02;
include secondary windows and absence paths. Read
[e2e_search_probe.py](../../../tests/ui/e2e_search_probe.py) and relevant tests.
Use inventory keys D1–D6. In particular, D5's
`test_installed_settings_users_publishes_builder_ids` performs a global
`search_button` activation despite missing provider application/surface IDs.
Migrate or contain that input before the full host adapter file is run; retain
its partial-ID observations as inventory, not interaction qualification.

1. Bind each target to actual public IDs scoped to provider application and
   surface. Preserve query/readback, focus, semantic actions, bounded output,
   document content, close/return and stable-absence assertions after lookup.
   No title, role, label, fixed key count or tree order may identify the target.
2. Missing provider mappings must refuse before discovery/input through the old
   path. Keep a named consumer and return condition in the existing
   [provider gap catalogue](../E2E-Building-Blocks.md#functional-validation).
   Do not install, patch or replace external providers, synthesize provider IDs,
   or bypass desktop interaction using service calls or host execution.
3. Retain the nested search probe as a refusal check for an unqualified provider.
   It does not qualify live search, typing or launch. Do not reintroduce direct
   overview operations; task 05 owns that helper and its remaining callers.
4. Any chooser, Settings, Files, archive or editor route found by the inventory
   gets the same disposition. Do not build a new integration without a named
   existing consumer or add scope for a hypothetical future scenario.

## Verification and completion

Run focused units, including:

```sh
tools/run-unit-tests -q 'tests/unit/test_accessible_e2e_ui.py' 'tests/unit/test_e2e_desktop_session.py' 'tests/unit/test_e2e_terminal.py' 'tests/unit/test_parent_about_worker.py' 'tests/unit/test_parent_access_worker.py'
```

Add other directly affected files. Retain original behavior checks on ID-capable
test doubles and separately prove refusal before input for missing IDs, wrong
owner/surface and ambiguity. Preserve terminal/session ownership and uncertain
delivery guards. Run the narrow host adapter UI check only if applicable and
safe under existing prerequisites; full host UI verification remains task 08.

Close each task-02 row as migrated or contained/provider blocked. A blocked
provider is not qualified by source review, unit success, scenario status or an
old name-based run. No installed desktop journey is executed in this session.
