"""Boundary and execution tests for all approved test category routes."""
import os
from pathlib import Path
import runpy
import sys
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import test_launcher as host
import test_commands as commands
sys.path.pop(0)


@pytest.fixture
def checkout(tmp_path):
    for category in ('unit', 'component', 'ui', 'child'):
        directory = tmp_path / 'tests' / category
        directory.mkdir(parents=True)
        (directory / 'test_future.py').touch()
    (tmp_path / 'tests/child/future.test.mjs').touch()
    (tmp_path / 'tests/child/future_test.js').touch()
    return tmp_path


@pytest.mark.parametrize('category', ['unit', 'component', 'ui'])
def test_future_paths_expand_only_in_category(checkout, category):
    assert host.selection(checkout, [f'tests/{category}/test_*.py::test_case[x*y]'], category) == [
        f'tests/{category}/test_future.py::test_case[x*y]']
    for other in ('system', 'e2e', 'integration'):
        with pytest.raises(ValueError):
            host.selection(checkout, [f'tests/{other}/test_future.py'], category)


@pytest.mark.parametrize('option', ['-c=/tmp/evil', '-p=evil', '--rootdir=/tmp',
                                    '--override-ini=addopts=-p evil', '--pyargs',
                                    '--junitxml=/etc/file', '--ignore=/tmp', '--timeout=0'])
def test_rejects_pytest_bypasses(checkout, option):
    with pytest.raises(ValueError):
        host.pytest_command(checkout, ['tests/component', option], 'component')


@pytest.mark.parametrize('value', ['0', '0s', '-1', 'NaN', 'inf', '3sms', '1;id', '--kill-after=0'])
def test_invalid_ui_timeout(value):
    with pytest.raises(ValueError):
        host.duration(value)


def test_ui_globs_environment_timeout_and_exclusions(checkout):
    python = checkout / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to('/usr/bin/python3')
    command = host.pytest_command(checkout, ['--timeout', '360s', 'tests/ui/test_*.py',
                                           '--ignore=tests/ui/test_future.py', '-q'], 'ui')
    assert command[:4] == ['/usr/bin/timeout', '--foreground', '360s', str(python)]
    assert '--ignore=tests/ui/test_future.py' in command
    assert command[-2:] == ['--', 'tests/ui/test_future.py']


def test_untrusted_environment_is_removed(checkout, monkeypatch):
    for key in ('PYTHONPATH', 'PYTEST_PLUGINS', 'PYTEST_ADDOPTS', 'LD_PRELOAD',
                'MAKEFLAGS', 'MAKEFILES', 'NODE_OPTIONS', 'GJS_PATH', 'BASH_ENV', 'CC'):
        monkeypatch.setenv(key, '/tmp/untrusted')
    env = host.environment(checkout)
    assert '/tmp/untrusted' not in env.values()
    assert env['PATH'] == '/usr/sbin:/usr/bin:/sbin:/bin'


def test_failed_cleanup_gates_component(checkout, monkeypatch):
    prerequisite = Mock(side_effect=ValueError('failed prerequisites'))
    execute = Mock()
    monkeypatch.setattr(host, 'prerequisites', prerequisite)
    monkeypatch.setattr(host.os, 'execve', execute)
    with pytest.raises(ValueError):
        host.run_host(checkout, 'component', [])
    prerequisite.assert_called_once_with(checkout)
    execute.assert_not_called()


@pytest.mark.parametrize('category', ['unit', 'component', 'ui'])
def test_collect_only_never_starts_cleanup(checkout, monkeypatch, category):
    python = checkout / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to('/usr/bin/python3')
    prerequisite = Mock()
    execute = Mock()
    monkeypatch.setattr(host, 'prerequisites', prerequisite)
    monkeypatch.setattr(host.os, 'execve', execute)
    monkeypatch.chdir(checkout)
    host.run_host(checkout, category, ['--collect-only'])
    prerequisite.assert_not_called()
    execute.assert_called_once()


@pytest.mark.parametrize('category,argv', [
    ('check', ['-f', '/tmp/evil']), ('check', ['SHELL=/tmp/evil']),
    ('all', ['--component=unit']), ('fast', ['--component=$(touch /tmp/no)']),
    ('fast', ['--type', 'a;id']), ('child-node', ['--eval=process.exit()']),
    ('child-gjs', ['tests/child/future.test.mjs']), ('static', ['/tmp/check.py']),
    ('traceability', ['--manifest=/tmp/input']), ('coverage', ['--cov=/tmp']),
    ('artifacts', ['build', '/etc/target']), ('fixtures', ['--output=/tmp/evil']),
])
def test_category_option_injection_rejected(checkout, category, argv):
    with pytest.raises(ValueError):
        commands.plan(checkout, category, argv)


def test_child_future_files_are_literal_and_need_no_policy_change(checkout):
    node, safety = commands.plan(checkout, 'child-node', ['tests/child/*.test.mjs'])
    assert node == [['/usr/bin/node', '--test', str(checkout / 'tests/child/future.test.mjs')]]
    assert safety is False
    gjs, _ = commands.plan(checkout, 'child-gjs', [])
    assert gjs == [['/usr/bin/gjs', '-m', str(checkout / 'tests/child/future_test.js')]]


def test_missing_roadmap_target_refuses_but_fixed_target_can_be_added(checkout):
    (checkout / 'Makefile').write_text('check:\n\ttrue\n')
    with pytest.raises(ValueError, match='not implemented'):
        commands.plan(checkout, 'fast', [])
    (checkout / 'Makefile').write_text('test-fast:\n\ttrue\n')
    plan, safety = commands.plan(checkout, 'fast', ['--component=broker', '--list'])
    assert plan[0][-3:] == ['test-fast', 'COMPONENT=broker', 'LIST=1']
    assert safety is False


def test_e2e_listing_is_host_safe_and_pending_execution_refused():
    plan, safety = commands.plan(ROOT, 'e2e', ['--list'])
    assert 'pkexec' not in plan[0][0]
    assert plan[0][2].endswith('/tests/e2e/runner.py')
    assert '--list' in plan[0]
    assert safety is False
    with pytest.raises(ValueError, match='selection:pending'):
        commands.plan(ROOT, 'e2e', ['--artifacts=/tmp/onpc-future'])


def test_privileged_parent_symlink_is_rejected(checkout):
    dispatcher = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))
    external = checkout / 'outside'
    external.mkdir()
    (external / 'check_future.py').touch()
    (checkout / 'tests/integration').symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError):
        dispatcher['selection'](checkout, ['integration', 'check_future'])


def test_backend_readiness_is_a_fixed_host_safe_command():
    plan, safety = commands.plan(ROOT, 'backend', [])
    assert plan == [['/usr/bin/python3', '-B', str(ROOT / 'tests/integration/graphical_backend.py')]]
    assert safety is False
    with pytest.raises(ValueError):
        commands.plan(ROOT, 'backend', ['--command=id'])
