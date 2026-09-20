"""Boundary and execution tests for all approved test category routes."""
import json
import os
import runpy
import subprocess
import sys
from unittest.mock import Mock

import pytest

from tests.support.paths import ROOT
import test_launcher as host
import test_commands as commands


def test_retention_permission_failure_identifies_allocation_without_starting_tests(
        tmp_path, monkeypatch, capsys):
    import regression
    import test_retention

    store = test_retention.Store(tmp_path / 'artifacts/test-retention')
    with store.session():
        scratch = tmp_path / 'sbuild-scratch'
        scratch.mkdir(mode=0o711)
        test_retention.retain(scratch, mode=0o711)
        private = scratch / 'private-chroot'
        private.mkdir(mode=0)
    journal = store.path / 'current.json'
    original = journal.read_bytes()
    monkeypatch.setattr(commands, '__file__', str(tmp_path / 'tools/test_commands.py'))
    monkeypatch.setattr(regression, 'retained_main',
                        lambda *args, **kwargs: pytest.fail('tests started despite inaccessible storage'))
    try:
        assert commands._main(['all']) == 2
        diagnostic = capsys.readouterr().err
        assert 'PermissionError' in diagnostic
        assert 'retention: cannot inspect registered allocation' in diagnostic
        assert repr(str(scratch)) in diagnostic
        assert 'startup refused' in diagnostic
        assert 'filesystem or execution failure' not in diagnostic
        assert journal.read_bytes() == original
        assert private.exists()
    finally:
        private.chmod(0o700)


@pytest.mark.parametrize('argv', [[], ['unknown', '--invalid'], ['unit', '-q']])
def test_external_invocation_reaches_session_before_argument_validation(monkeypatch, argv):
    import regression_session
    import test_activity
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    monkeypatch.delenv(test_activity.VARIABLE, raising=False)
    monkeypatch.setattr(test_activity, '_descriptor', None)
    attach = Mock(return_value=7)
    monkeypatch.setattr(regression_session, 'main', attach)
    monkeypatch.setattr(commands, 'validate', Mock(side_effect=AssertionError('premature validation')))
    assert commands.main(argv) == 7
    attach.assert_called_once_with(ROOT, argv)


def test_internal_worker_uses_verified_activity_instead_of_attaching(tmp_path, monkeypatch):
    import regression_session
    import test_activity
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(commands, '__file__', str(tmp_path / 'tools/test_commands.py'))
    monkeypatch.setattr(commands, 'validate', Mock())
    attach = Mock(side_effect=AssertionError('worker attached to its own session'))
    monkeypatch.setattr(regression_session, 'main', attach)
    execute = Mock(return_value=7)
    monkeypatch.setattr(commands, '_main', execute)
    with test_activity.activity(tmp_path):
        assert commands.main(['static', 'shell']) == 7
    execute.assert_called_once_with(['static', 'shell'])


def test_detached_coverage_keeps_report_configuration(tmp_path, monkeypatch):
    import regression_process
    monkeypatch.setattr(commands, 'plan', lambda *_: ([['pytest', '--', 'tests/unit']], False))
    monkeypatch.setattr('tempfile.mkdtemp', lambda **_: str(tmp_path))
    execute = Mock(return_value=0)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    assert regression_process.category_run(ROOT, 'coverage', [], pipe=False) == 0
    assert execute.call_args.args[0] == [
        'pytest', '--cov-report=xml:' + str(tmp_path) + '/coverage.xml', '--', 'tests/unit']
    assert execute.call_args.kwargs['env']['COVERAGE_FILE'] == str(tmp_path) + '/.coverage'


def test_detached_e2e_failed_build_never_starts_privileged_runner(tmp_path, monkeypatch):
    import regression_process
    monkeypatch.setattr(commands, 'plan', lambda *_: (
        [['/usr/bin/pkexec', '/usr/local/libexec/onpc-test-runner', 'e2e']], False))
    monkeypatch.setattr('tempfile.mkdtemp', lambda **_: str(tmp_path))
    execute = Mock(return_value=130)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    assert regression_process.category_run(ROOT, 'e2e', [], pipe=False) == 130
    execute.assert_called_once()
    assert execute.call_args.args[0][2].endswith('/tools/build_test_artifacts.py')


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


def test_pytest_storage_does_not_inherit_ramdisk_or_caller_override(checkout, monkeypatch):
    for key in ('TMPDIR', 'TMP', 'TEMP'):
        monkeypatch.setenv(key, '/tmp/untrusted')
    env = host.test_environment(checkout)
    assert env['TMPDIR'] == '/var/tmp'
    assert 'TMP' not in env and 'TEMP' not in env
    probe = checkout / 'storage_probe.py'
    probe.write_text('''import os, pathlib, tempfile
with tempfile.TemporaryDirectory(prefix='onpc-storage-probe-') as directory:
    assert pathlib.Path(directory).parent == pathlib.Path('/var/tmp')
    with tempfile.TemporaryFile() as capture:
        assert os.readlink('/proc/self/fd/' + str(capture.fileno())).startswith('/var/tmp/')
        capture.write(b'captured output')
        capture.seek(0)
        assert capture.read() == b'captured output'
''')
    subprocess.run([sys.executable, '-B', str(probe)], env=env, check=True, timeout=10)
    # Keep build/controller environments separate from the host pytest policy.
    assert 'TMPDIR' not in host.environment(checkout)


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
    assert node == [['/usr/bin/node', '--test', '--test-concurrency=2', str(checkout / 'tests/child/future.test.mjs')]]
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
        commands.plan(ROOT, 'e2e', ['--scenario=E2E-002', '--artifacts=/tmp/onpc-future'])


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


@pytest.mark.parametrize('argv', [['--help'], ['-h']])
def test_help_prints_complete_categories_and_combinations(capsys, argv):
    assert commands._main(argv) == 0
    text = capsys.readouterr().out
    assert text == commands.usage() + '\n'
    assert text.startswith('Usage: tools/run-tests')
    assert 'host and e2e' in text
    assert 'all = host + system + e2e' in text
    assert 'tools/run-tests system e2e' in text
    assert 'tools/run-tests host system e2e' in text
    assert 'two package builds and reproducibility' in text
    assert not text.lstrip().startswith('{')


def test_list_still_prints_category_json(capsys):
    assert commands._main(['--list']) == 0
    assert json.loads(capsys.readouterr().out) == commands.CATEGORIES


@pytest.mark.parametrize('argv', [['--help'], ['-h'], ['--list']])
def test_public_global_inspection_bypasses_activity_and_session(monkeypatch, capsys, argv):
    import regression_session

    def refuse(*args, **kwargs):
        pytest.fail('inspection must return before activity or session inspection')

    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(commands.test_activity, 'descriptors', refuse)
    monkeypatch.setattr(regression_session, 'main', refuse)
    assert commands.main(argv) == 0
    output = capsys.readouterr().out
    if argv == ['--list']:
        assert json.loads(output) == commands.CATEGORIES
    else:
        assert output == commands.usage() + '\n'


@pytest.mark.parametrize('argv', [
    ['unit', '--collect-only'], ['component', '--help'], ['ui', '-h'],
    ['fast', '--list'], ['system', '--list'], ['e2e', '--list'],
])
def test_public_category_inspection_bypasses_activity_and_session(monkeypatch, argv):
    import regression_session

    def refuse(*args, **kwargs):
        pytest.fail('inspection must return before activity or session inspection')

    execute = Mock(return_value=7)
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(commands.test_activity, 'descriptors', refuse)
    monkeypatch.setattr(regression_session, 'main', refuse)
    monkeypatch.setattr(commands, '_main', execute)
    assert commands.main(argv) == 7
    execute.assert_called_once_with(argv)


def test_empty_argv_dispatches_the_all_aggregate(monkeypatch):
    import regression
    execute = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', execute)
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    assert commands._main([]) == 7
    execute.assert_called_once_with(ROOT, verify_backing_bytes=False)


@pytest.mark.parametrize('category,verify', [('all', False), ('all-verify', True)])
def test_aggregate_dispatch_selects_policy_and_rejects_narrowing(monkeypatch, category, verify):
    import regression
    execute = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', execute)
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    assert commands._main([category]) == 7
    execute.assert_called_once_with(ROOT, verify_backing_bytes=verify)
    execute.reset_mock()
    assert commands._main([category, '--skip-backing-verification']) == 2
    execute.assert_not_called()


@pytest.mark.parametrize('category', ['all', 'all-verify', 'host', 'host-builds'])
def test_continue_on_errors_is_a_valueless_aggregate_flag(monkeypatch, category):
    import regression
    execute = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', execute)
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    assert commands._main([category, '--continue-on-errors']) == 7
    assert execute.call_args.kwargs['continue_on_errors'] is True
    if category == 'host-builds':
        assert execute.call_args.kwargs['serial_builds'] is False
        for args in (['--serial-builds', '--continue-on-errors'],
                     ['--continue-on-errors', '--serial-builds']):
            assert commands._main([category, *args]) == 7
            assert execute.call_args.kwargs['serial_builds'] is True
    execute.reset_mock()
    for args in (['--continue-on-errors=true'], ['--continue-on-errors', 'true'],
                 ['--continue-on-errors', '--continue-on-errors']):
        assert commands._main([category, *args]) == 2
    execute.assert_not_called()


def test_host_aggregate_dispatch_and_invalid_arguments(monkeypatch):
    import regression
    execute = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', execute)
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    assert commands._main(['host']) == 7
    execute.assert_called_once_with(ROOT, phases=('host',), verify_backing_bytes=False)
    execute.reset_mock()
    for args in (['--skip-backing-verification'], ['--component=ui'], ['--unattended']):
        assert commands._main(['host', *args]) == 2
    execute.assert_not_called()


@pytest.mark.parametrize('serial', [False, True])
def test_host_build_qualification_is_fixed_and_never_dispatches_vm(monkeypatch, serial):
    import regression
    execute = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', execute)
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    args = ['--serial-builds'] if serial else []
    assert commands._main(['host-builds', *args]) == 7
    execute.assert_called_once_with(ROOT, phases=('host',), serial_builds=serial)
    execute.reset_mock()
    for extra in (['--serial'], ['--serial-builds', '--serial-builds'], ['--area', 'session'],
                  ['--skip-backing-verification'], ['--command=id']):
        assert commands._main(['host-builds', *extra]) == 2
    execute.assert_not_called()


@pytest.mark.parametrize('argv', [
    ['host'], ['system'], ['e2e'], ['host', 'system'], ['host', 'e2e'],
    ['system', 'e2e'], ['host', 'system', 'e2e'], ['e2e', 'host', 'system'],
    ['e2e', 'system'], ['system', 'host'], ['e2e', 'host'],
])
@pytest.mark.parametrize('detached', [False, True])
def test_complete_categories_share_one_ordered_aggregate(monkeypatch, argv, detached):
    import regression
    execute = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', execute)
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    phases = tuple(kind for kind in ('host', 'system', 'e2e') if kind in argv)
    for flag in ([], ['--continue-on-errors']):
        commands.validate(ROOT, [*argv, *flag])
        assert commands.selections(ROOT, [*argv, *flag]) == [(kind, []) for kind in phases]
        assert commands._main([*argv, *flag], detached=detached) == 7
        options = {'continue_on_errors': True} if flag else {}
        execute.assert_called_with(ROOT, phases=phases, verify_backing_bytes='host' not in phases,
                                   **options)


@pytest.mark.parametrize('argv', [
    ['host', 'host'], ['system', 'e2e', 'system'], ['all', 'host'],
    ['host', 'system', '--bad'], ['host', 'system', '--list'],
    ['host', 'system', '--continue-on-errors', '--continue-on-errors'],
])
def test_invalid_complete_combinations_are_refused_before_work(argv):
    with pytest.raises(ValueError):
        commands.validate(ROOT, argv)
