# 05 — Close retained image, pointer and direct Shell routes

**Recommended model: GPT-6 Astra. Effort: high.** This slice crosses Python/Perl
dispatch, input acknowledgements and safety guards, including legacy callers.

**Prerequisite:** [03](03-authentication-surfaces.md) and
[04](04-desktop-and-external-apps.md) dispositions recorded; [shared preflight](README.md).
**Status:** Not started. **Next:** [06](06-fixture-lifecycle.md).

## Scope and work

Read [onpc_journey.pm](../../../tests/integration/graphical_smoke/lib/onpc_journey.pm),
[onpc_pointer.pm](../../../tests/integration/graphical_smoke/lib/onpc_pointer.pm),
[shell_overview.py](../../../tests/ui/shell_overview.py), and all their callers.
Also trace `pointer_target`, `pointer_glyph`, `stable_pointer` and `ui_pointer`
dispatch/recording in [the guest adapter](../../../tests/e2e/accessible_ui.py) and
the installed journey controller. Include retained Parent login and system-prompt
cancellation paths; pending scenario metadata is not an execution guard.
Use frozen inventory keys L1–L10. Newly recorded bypasses include
`onpc_vt6.authenticate/inspect_prompt`, direct image/input branches in
`smoke.pm.run`, and `onpc_parent_about.read_footer`'s Tab/End path. Review those
callers explicitly, including retained qualification/review modes. VT6 image
recipient proof is distinct from the supported serial proof; lack of a usable
public identity must refuse that VT6 route without changing serial behavior.

1. Replace image-based `observe`/`seen` gates, image clicks and coordinate input
   with the qualified ID action/observation route where one exists. Preserve each
   caller's behavioral assertion, stage ordering, acknowledgement and durable
   evidence semantics. A screenshot may remain diagnostic evidence only.
2. Where the provider is blocked, make the callable route refuse before image
   matching, geometry/backend access or input. Preserve behavior obligations and
   unit coverage; do not simply delete the helper and its tests or mark tests
   skipped. Prove indirect dispatch cannot reach the prohibited mechanism.
3. Migrate `shell_overview.set_overview` and callers away from the direct
   `OverviewActive` D-Bus route. Only an ID-qualified public interaction can
   establish customer overview state. Without provider IDs, report the named
   blocked consumer. Keep owned nested-bus validation and cleanup safeguards;
   ownership alone does not qualify the old input route.
4. Audit the final dispatch/call graph for remaining label/role discovery,
   image thresholds, extents, coordinates, tree-position navigation and direct
   Shell state manipulation. Distinguish ordinary product rendering or retained
   diagnostic screenshots from prohibited automated selection/acceptance.

## Verification and completion

Use focused unit selections, including relevant cases in
`tests/unit/test_graphical_smoke.py`, `test_accessible_e2e_ui.py`,
`test_child_preview.py`, `test_mutter_input.py`, and the changed journey/graphical
cleanup-safety files. Invoke them as literal full paths through
`tools/run-unit-tests`; do not execute graphical integration/VM scripts.

Retain actual Perl adapter execution in unit harnesses where already provided.
Prove refusal precedes backend calls and acknowledgement, and preserve
secret-recipient, ownership, disconnect and uncertain-input guards. Do not
replay an uncertain input to achieve a passing assertion.

Complete when no known callable route can execute prohibited targeting/input,
the task-02 inventory has no unassigned legacy row, and every blocked consumer
has an exact provider return condition. This is host/source remediation, not
installed journey acceptance. Record any unresolved safety issue as a blocker
for task 07, not as harmless legacy code.
