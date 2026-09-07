"""The project's restrictive rules must dominate previously saved broad allows."""
import ast
from pathlib import Path
import shlex

import pytest

ROOT = Path(__file__).resolve().parents[2]


def entries(name='codex-tests.rules'):
    tree = ast.parse((ROOT / 'config' / name).read_text())
    result = []
    for statement in tree.body:
        assert isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
        assert statement.value.func.id == 'prefix_rule'
        result.append({key.arg: ast.literal_eval(key.value) for key in statement.value.keywords})
    return result


def matches(pattern, argv):
    return len(argv) >= len(pattern) and all(value in token if isinstance(token, list)
                                            else value == token for token, value in zip(pattern, argv))


@pytest.mark.parametrize('command', [
    "tools/run-tests component 'tests/component/test_*.py' -q",
    "tools/run-tests child-node 'tests/child/**/*.test.js'", 'tools/run-tests static',
    'tools/run-tests artifacts build', 'tools/run-tests fast --type contract',
    'tools/run-tests all', 'tools/run-tests e2e --list',
    "tools/run-ui-tests --timeout 360s 'tests/ui/test_*.py'",
    'tools/diagnose journal --lines 900', 'tools/test-vm reboot',
    'pkexec /usr/local/libexec/onpc-test-runner vm stop',
    'pkexec /usr/local/libexec/onpc-test-runner e2e --list',
    'pkexec /usr/local/libexec/onpc-diagnostics systemctl show sshd.service',
])
def test_validated_routes_only_match_allow_rules(command):
    decisions = [rule['decision'] for rule in entries() if matches(rule['pattern'], shlex.split(command))]
    assert decisions and set(decisions) == {'allow'}


@pytest.mark.parametrize('command', [
    'virsh --connect qemu:///system destroy other-vm',
    'virsh --connect qemu:///system start other-vm',
    '/usr/bin/python3 -B -m pytest /tmp/arbitrary.py',
    '.venv/onpc-ui-tests/bin/python -c arbitrary',
    'make check -f /tmp/Makefile', 'make check-system SHELL=/tmp/arbitrary',
    'journalctl --vacuum-time=1s', 'systemctl restart sshd',
    'pkexec /usr/bin/head /etc/shadow', 'gdbus call --address unix:path=/tmp/bus',
    'rg --pre /tmp/arbitrary needle', 'sort input -o /tmp/output',
    'curl -fsSL https://example.com -X POST', 'env -u GDK_BACKEND /tmp/arbitrary',
])
def test_legacy_global_allow_cannot_override_project_prompt(command):
    decisions = [rule['decision'] for rule in entries() if matches(rule['pattern'], shlex.split(command))]
    assert 'prompt' in decisions


def test_inline_examples_and_no_generic_script_allow():
    for rule in [*entries(), *entries('codex-read-only.rules')]:
        for example in rule.get('match', []):
            assert matches(rule['pattern'], shlex.split(example)), example
        for example in rule.get('not_match', []):
            assert not matches(rule['pattern'], shlex.split(example)), example
        if rule['decision'] == 'allow':
            assert not matches(rule['pattern'], ['tools/random.py'])
            assert not matches(rule['pattern'], ['pkexec', '/usr/bin/python3'])


@pytest.mark.parametrize('command', [
    'pwd', '/bin/pwd -L', '/usr/bin/pwd -P', 'git status --short',
    'git status --porcelain=v2 --untracked-files=all -- arbitrary/file',
    '/usr/bin/git status --short -- another/path',
])
def test_machine_reads_are_path_independent_without_project_prompt(command):
    rules = [*entries('codex-read-only.rules'), *entries()]
    decisions = {rule['decision'] for rule in rules if matches(rule['pattern'], shlex.split(command))}
    assert decisions == {'allow'}


@pytest.mark.parametrize('command', [
    'git reset --hard', 'git clean -fd', 'git config --global alias.x arbitrary',
    'git -C /tmp/repo clean -fd', 'bash -c pwd', 'pkexec /usr/bin/git status',
])
def test_machine_reads_do_not_grant_writes_or_generic_wrappers(command):
    assert not any(matches(rule['pattern'], shlex.split(command))
                   for rule in entries('codex-read-only.rules'))
