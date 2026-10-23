"""Product execution-policy compatibility with the maintained E2E fixtures."""


def test_policy_qualification_pattern_is_representable_with_baseline_fixtures(tmp_path):
    from pathlib import Path
    from oh_no_parent_control.execution_policy import FapolicydPolicy
    from tests.fixtures.build_test_applications import NATIVE_NAMES
    from policy_qualification import PLAN as policy_plan

    for name in NATIVE_NAMES:
        target = tmp_path / name
        target.write_bytes(b'\x7fELF fixture ' + name.encode())
        target.chmod(0o755)
    pattern = str(tmp_path / Path(policy_plan.match_checks['filtered-match']).name)
    issues = []
    rules = FapolicydPolicy.render(
        {1002: (str(tmp_path / NATIVE_NAMES[0]),)}, {1002: (pattern,)}, issues=issues)
    assert issues == []
    assert f'deny_syslog perm=execute uid=1002 : dir={tmp_path}/' in rules
