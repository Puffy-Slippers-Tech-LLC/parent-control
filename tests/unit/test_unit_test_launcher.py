"""Selection and execution boundaries for the persistently approved unit launcher."""

from pathlib import Path
import os
import runpy
import shutil
import subprocess
import time
from unittest.mock import Mock

import pytest


LAUNCHER = Path(__file__).resolve().parents[2] / 'tools/run-unit-tests'
runner = runpy.run_path(str(LAUNCHER.with_name('test_launcher.py')))


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    import test_source
    for key in (test_source.VARIABLE, test_source.WRITER, test_source.IMPORTS):
        monkeypatch.delenv(key, raising=False)
    root = tmp_path / 'checkout'
    unit = root / 'tests/unit'
    unit.mkdir(parents=True)
    (unit / 'test_z_cleanup_safety.py').write_text('def test_z(): pass\n')
    (unit / 'test_a_cleanup_safety.py').write_text('def test_a(): pass\n')
    (unit / 'test_graphical_lease.py').write_text('def test_lease(): pass\n')
    (unit / 'helper.py').touch()
    (root / 'tools').mkdir()
    shutil.copy2(LAUNCHER, root / 'tools/run-unit-tests')
    shutil.copy2(LAUNCHER.with_name('run-tests'), root / 'tools/run-tests')
    # Exercise the real shared session/observer dependencies in this private
    # checkout, without accessing the development checkout's active session.
    for module in LAUNCHER.parent.glob('*.py'):
        shutil.copy2(module, root / 'tools' / module.name)
    (root / 'tests/conftest.py').write_text(
        'from tools.regression_events import (pytest_collection_finish, pytest_collectreport,\n'
        '    pytest_runtest_logreport, pytest_sessionfinish, pytest_collection_modifyitems)\n')
    integration = root / 'tests/integration'
    integration.mkdir()
    shutil.copy2(LAUNCHER.parents[1] / 'tests/integration/vm_config.py', integration / 'vm_config.py')
    return root


def test_globs_expand_sorted_with_explicit_files_and_duplicates(checkout):
    assert runner['selection'](checkout, [
        'tests/unit/test_*cleanup_safety.py', 'tests/unit/test_graphical_lease.py',
        './tests/unit/test_a_cleanup_safety.py',
    ]) == [
        'tests/unit/test_a_cleanup_safety.py', 'tests/unit/test_z_cleanup_safety.py',
        'tests/unit/test_graphical_lease.py',
    ]


def test_controller_startup_guards_lazy_imports_and_refuses_stale_admission(checkout):
    # Exercise the real public wrapper and selection. The import hook schedules
    # one independent repair precisely at the reset-gate handoff; it replaces
    # neither the controller nor the source service.
    probe = '''import builtins, runpy, sys
from contextlib import contextmanager
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root / 'tools'))
import test_source
source = test_source.SourceProtection(test_source.source_directory(root))
original = builtins.__import__
seen = set()
def observed(name, *args, **kwargs):
    if name in ('vm_selection', 'regression_session') and name not in seen:
        seen.add(name)
        with test_source._lock(source.directory / 'repair-owner') as writer, source.state():
            assert not source.admit(writer, owner=str(root / 'repair')), name
    module = original(name, *args, **kwargs)
    if name == 'test_reset' and name not in seen:
        seen.add(name)
        startup = module.startup
        @contextmanager
        def interleaved(root):
            assert not test_source.descriptors()
            with test_source._lock(source.directory / 'repair-owner') as writer, source.state():
                owner = str(root / 'repair')
                assert source.admit(writer, owner=owner)
                source.finish(owner, changed=True)
            with startup(root):
                yield
        module.startup = interleaved
    return module
builtins.__import__ = observed
sys.argv = [str(root / 'tools/run-unit-tests'), 'tests/unit/test_a_cleanup_safety.py']
try:
    runpy.run_path(sys.argv[0], run_name='__main__')
except SystemExit as error:
    assert error.code == 2, error.code
else:
    raise AssertionError('stale controller admitted work')
assert seen == {'vm_selection', 'regression_session', 'test_reset'}, seen
assert not list((root / 'output/test-runs').rglob('current.json'))
'''
    result = subprocess.run(['/usr/bin/python3', '-B', '-c', probe, str(checkout)],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert 'source changed after startup' in result.stderr


@pytest.mark.parametrize('control', ['--reload', '--reset'])
def test_control_startup_reimports_before_new_execution(checkout, control):
    # Replace already-imported controller bytes during control startup. Only a
    # fresh interpreter can execute the new entry, under its inherited lease.
    replacement = checkout / 'fresh-controller.py'
    replacement.write_text('''
def main(argv=None):
    import fcntl
    import test_source
    root = Path(__file__).resolve().parents[1]
    assert '--reload' not in sys.argv and '--reset' not in sys.argv
    source = test_source.SourceProtection(test_source.source_directory(root))
    descriptor = int(test_source.environment()[test_source.VARIABLE])
    source.validate(descriptor, held=True)
    assert source.generation() >= 1
    assert not list((root / 'output/test-runs').rglob('current.json'))
    for directory in ('state', 'sessions-host'):
        path = root / 'output/test-runs/host' / directory
        gate = path / ('test-startup-gate' if directory == 'state' else 'gate')
        if gate.exists():
            with test_source._lock(gate) as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    test_source.finish_admission()
    assert not test_source.descriptors() and test_source.IMPORTS not in os.environ
    with test_source._lock(source.directory / 'repair-owner') as writer, source.state():
        assert source.admit(writer, owner=str(root / 'fresh-check'))
        source.finish(str(root / 'fresh-check'))
    (root / 'fresh-execution').write_text(str(os.getpid()))
    return 0
''')
    probe = '''import builtins, os, runpy, subprocess, sys
from pathlib import Path
root, control, replacement = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
sys.path.insert(0, str(root / 'tools'))
import test_source
source = test_source.SourceProtection(test_source.source_directory(root))
original = builtins.__import__
changed = False
def observed(name, *args, **kwargs):
    global changed
    if name == 'regression_session' and not changed:
        changed = True
        with test_source._lock(source.directory / 'repair-owner') as writer, source.state():
            owner = str(root / 'repair')
            assert source.admit(writer, owner=owner)
            target = root / 'tools/test_commands.py'
            target.write_text(target.read_text() + replacement.read_text())
            source.finish(owner, changed=True)
    return original(name, *args, **kwargs)
builtins.__import__ = observed
if control == '--reset':
    # Real reset owns only this synthetic checkout. Its external recovery
    # boundary is a successful host-only fixture, never a real cleanup command.
    run = subprocess.run
    def recovered(command, *args, **kwargs):
        if command[0] == str(root / 'tools/cleanup-e2e'):
            assert command[1:] == ['--host-only']
            (root / 'recovered').touch()
            return subprocess.CompletedProcess(command, 0)
        return run(command, *args, **kwargs)
    subprocess.run = recovered
(root / 'initial-pid').write_text(str(os.getpid()))
sys.argv = [str(root / 'tools/run-tests'), control, 'unit', 'tests/unit/test_a_cleanup_safety.py']
runpy.run_path(sys.argv[0], run_name='__main__')
'''
    result = subprocess.run(['/usr/bin/python3', '-B', '-c', probe,
                             str(checkout), control, str(replacement)],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert (checkout / 'fresh-execution').read_text() == (checkout / 'initial-pid').read_text()
    assert (checkout / 'recovered').exists() == (control == '--reset')


@pytest.mark.parametrize('pattern', ['test_?_*safety.py', 'test_[az]_cleanup_safety.py'])
def test_other_filename_globs(checkout, pattern):
    assert len(runner['selection'](checkout, ['tests/unit/' + pattern])) == 2


def test_nested_glob_and_node_suffix_stays_literal(checkout):
    nested = checkout / 'tests/unit/nested'
    nested.mkdir()
    (nested / 'test_case.py').touch()
    node = '::test_case[a*b?[$(echo nope); text]]'
    assert runner['selection'](checkout, ['tests/unit/**/test_case.py' + node]) == [
        'tests/unit/nested/test_case.py' + node,
    ]


@pytest.mark.parametrize('selector', [
    '', '.', '/tmp/test_external.py', 'tests/component/test_case.py',
    'tests/unit/../component/test_case.py', 'tests/unit/missing.py',
    'tests/unit/test_no_match*.py', 'tests/unit/helper.py',
    'tests/unit::test_case', 'tests/unit/test_graphical_lease.py::',
    'tests/unit/test_graphical_lease.py\n',
])
def test_invalid_selector_rejected_even_with_valid_selection(checkout, selector):
    with pytest.raises(ValueError):
        runner['selection'](checkout, ['tests/unit/test_graphical_lease.py', selector])


@pytest.mark.parametrize('selector', [
    'tests/unit', 'tests/unit/test_*.py', 'tests/unit/test_link.py',
])
def test_rejects_external_symlink_in_file_glob_or_directory(checkout, selector):
    outside = checkout.parent / 'test_external.py'
    outside.touch()
    (checkout / 'tests/unit/test_link.py').symlink_to(outside)
    with pytest.raises(ValueError):
        runner['selection'](checkout, [selector])


@pytest.mark.parametrize('selector', ['tests/unit', 'tests/unit/linked/test_case.py'])
def test_rejects_symlink_directory(checkout, selector):
    outside = checkout.parent / 'external'
    outside.mkdir()
    (outside / 'test_case.py').touch()
    (checkout / 'tests/unit/linked').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        runner['selection'](checkout, [selector])


def test_rejects_symlink_unit_root(checkout):
    unit = checkout / 'tests/unit'
    moved = checkout / 'tests/moved'
    unit.rename(moved)
    unit.symlink_to(moved, target_is_directory=True)
    with pytest.raises(ValueError):
        runner['selection'](checkout, ['tests/unit/test_graphical_lease.py'])


def test_options_can_be_interspersed_with_paths():
    selectors, options = runner['arguments']([
        '-q', 'tests/unit/test_one.py', '-vv', '-k', 'alpha or beta',
        'tests/unit/test_two.py', '-m', 'unit', '--maxfail=2', '--tb', 'short',
        '--collect-only', '--disable-warnings', '--durations', '0', '-x', '-s',
    ])
    assert selectors == ['tests/unit/test_one.py', 'tests/unit/test_two.py']
    assert options == [
        '-q', '-v', '-v', '-x', '-s', '--collect-only', '--disable-warnings',
        '-k=alpha or beta', '-m=unit', '--maxfail=2', '--durations=0', '--tb=short',
    ]


def test_defaults_to_whole_unit_directory():
    assert runner['arguments']([]) == (['tests/unit'], [])


@pytest.mark.parametrize('arguments', [
    ['-c', '/tmp/config.ini'], ['-p', 'external_plugin'], ['--pyargs', 'package'],
    ['--rootdir=/tmp'], ['--override-ini', 'testpaths=/tmp'],
    ['--junitxml=/tmp/output.xml'], ['@/tmp/arguments'],
    ['--maxfail=-1'], ['--durations', 'invalid'], ['--tb', 'invalid'],
    ['--col'], ['-k'],
])
def test_rejects_unsupported_or_invalid_options(checkout, arguments):
    with pytest.raises(ValueError):
        selectors, _ = runner['arguments'](arguments)
        runner['selection'](checkout, selectors)


def test_main_validates_all_selections_before_exec_and_redacts_values(checkout, monkeypatch, capsys):
    main = runner['main']
    monkeypatch.setitem(main.__globals__, '__file__', str(checkout / 'tools/run-unit-tests'))
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    execute = Mock()
    monkeypatch.setattr(os, 'execve', execute)
    for arguments in ([
        'tests/unit/test_graphical_lease.py', 'tests/unit/test_private_sentinel*.py',
    ], ['--tb=private_sentinel']):
        assert main(arguments) == 2
        assert 'private_sentinel' not in capsys.readouterr().err
    execute.assert_not_called()


def test_refuses_root_execution(monkeypatch, capsys):
    monkeypatch.setattr(os, 'geteuid', lambda: 0)
    execute = Mock()
    monkeypatch.setattr(os, 'execve', execute)
    assert runner['main'](['tests/unit']) == 2
    assert 'unprivileged user' in capsys.readouterr().err
    execute.assert_not_called()


def test_public_unit_execution_publishes_serial_watch_session(checkout, monkeypatch):
    import regression_session
    import test_activity
    main = runner['main']
    monkeypatch.setitem(main.__globals__, '__file__', str(checkout / 'tools/run-unit-tests'))
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    monkeypatch.delenv(test_activity.VARIABLE, raising=False)
    monkeypatch.setattr(test_activity, '_descriptor', None)
    attach = Mock(return_value=7)
    monkeypatch.setattr(regression_session, 'main', attach)
    assert main(['tests/unit/test_graphical_lease.py', '-q']) == 7
    attach.assert_called_once_with(checkout, [
        'unit', '--unattended', 'tests/unit/test_graphical_lease.py', '-q'])


def test_owned_unit_worker_does_not_reattach(checkout, monkeypatch):
    import regression_session
    import test_activity
    main = runner['main']
    monkeypatch.setitem(main.__globals__, '__file__', str(checkout / 'tools/run-unit-tests'))
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(regression_session, 'main', Mock(side_effect=AssertionError('reattached')))
    execute = Mock(return_value=3)
    monkeypatch.setitem(main.__globals__, 'run_host', execute)
    with test_activity.activity(checkout, host_only=True):
        assert main(['tests/unit/test_graphical_lease.py']) == 3
    execute.assert_called_once_with(checkout, 'unit', ['tests/unit/test_graphical_lease.py'])


@pytest.mark.parametrize('entry', [
    ['run-unit-tests'], ['run-tests', 'unit'],
    ['run-ui-tests'], ['run-tests', 'ui'],
])
def test_collection_succeeds_while_another_host_run_owns_checkout(checkout, entry):
    import test_activity
    from test_storage import scratch_descriptors

    category = 'ui' if 'ui' in entry or entry == ['run-ui-tests'] else 'unit'
    if category == 'ui':
        shutil.copy2(LAUNCHER.with_name('run-ui-tests'), checkout / 'tools/run-ui-tests')
        python = checkout / '.venv/onpc-ui-tests/bin/python'
        python.parent.mkdir(parents=True)
        python.symlink_to('/usr/bin/python3')
    tests = checkout / 'tests' / category
    tests.mkdir(exist_ok=True)
    (tests / 'test_collection.py').write_text(
        'import pytest\n'
        '@pytest.fixture(autouse=True)\n'
        'def never_run(): raise AssertionError("collection ran a fixture")\n'
        'def test_selected(): raise AssertionError("collection ran a test")\n'
        '@pytest.mark.live_e2e\n'
        'def test_live(): raise AssertionError("collection ran a live test")\n')
    environment = runner['test_environment'](checkout)
    environment['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    with test_activity.activity(checkout, host_only=True):
        test_activity.record_cleanup('a' * 64)
        result = subprocess.run(
            [str(checkout / 'tools' / entry[0]), *entry[1:],
             f'tests/{category}/test_collection.py', '--collect-only', '-q'],
            cwd=checkout, env=environment, pass_fds=scratch_descriptors(),
            capture_output=True, text=True, timeout=20, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'test_collection.py::test_selected' in result.stdout
        assert ('test_collection.py::test_live' in result.stdout) == (category == 'unit')
        # Inspection must not disturb the execution owner's lock or cleanup record.
        assert test_activity.cleanup_verified(checkout)


def test_detached_direct_unit_request_keeps_serial_flag_in_shared_report(monkeypatch):
    import regression
    import regression_process
    import test_commands
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(test_commands, 'selections', lambda *_: [
        ('unit', ['--unattended', '-q'])])
    report = Mock(return_value=5)
    monkeypatch.setattr(regression, 'main', report)
    execute = Mock(return_value=5)
    monkeypatch.setattr(regression_process, 'host_run', execute)
    assert test_commands._main(['unit', '--unattended', '-q'], detached=True) == 5
    report.assert_called_once_with(LAUNCHER.parents[1], selections=[('unit', ['--unattended', '-q'])])
    execute.assert_not_called()


@pytest.mark.parametrize('body,options,expected', [
    ('def test_pass(): pass\n', [], 0),
    ('def test_fail(): assert False\n', [], 1),
    ('def test_pass(): pass\n', ['-k', 'no_such_test'], 5),
    ('def test_pass(): pass\n', ['--collect-only'], 0),
])
def test_real_launcher_from_other_cwd_preserves_pytest_status(
        checkout, monkeypatch, body, options, expected):
    # Each private checkout owns its session and pytest child. The observer waits
    # for the detached owner's result before the fixture can be reclaimed.
    # Terminal evidence needs hundreds of paced journal flushes even for one
    # failed test. Advance only the private journal clock through those waits;
    # keep real fsync, observer clocks and the 20-second deadlock guard. Journal
    # spacing and sync failures have focused coverage in test_regression_session.
    journal_io = checkout / 'tools/test_io.py'
    with journal_io.open('a') as stream:
        stream.write('''

_real_journal_time = time

class _JournalClock:
    offset = 0.0

    def monotonic(self):
        return _real_journal_time.monotonic() + self.offset

    def sleep(self, delay):
        self.offset += delay

time = _JournalClock()
''')
    (checkout / 'tests/unit/test_status.py').write_text(body)
    subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
    (checkout / '.git/info/exclude').write_text('output/\n')
    monkeypatch.setenv('PYTEST_DISABLE_PLUGIN_AUTOLOAD', '1')
    monkeypatch.setenv('PYTEST_ADDOPTS', '--rootdir=/missing-private-sentinel')
    monkeypatch.setenv('PYTEST_PLUGINS', 'missing_private_sentinel')
    # Make recipes require the completed verdict; independent launches only
    # acknowledge admission. Keep this independent of the outer test command.
    monkeypatch.delenv('MAKELEVEL', raising=False)
    if expected == 1:
        monkeypatch.setenv('MAKELEVEL', '1')
    try:
        result = subprocess.run(
            [str(checkout / 'tools/run-unit-tests'), 'tests/unit/test_stat*.py', '-q', *options],
            cwd=checkout.parent, capture_output=True, text=True, timeout=20, check=False)
    except subprocess.TimeoutExpired as error:
        from test_storage import directory
        sessions = directory('sessions-host', root=checkout, create=False)
        diagnostics = []
        for path in sorted(sessions.glob('*/output')):
            run = path.parent
            result_path = run / 'result'
            diagnostics.append(
                f'Nested session {run.name}: result='
                f'{result_path.read_text() if result_path.exists() else "missing"}; '
                f'delivered={(run / "delivered").exists()}\n'
                + path.read_text(errors='replace')[-16384:])
        stderr = error.stderr or b''
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors='replace')
        error.add_note('Private launcher timeout diagnostics:\n' + stderr[-16384:]
                       + '\n' + '\n'.join(diagnostics))
        raise
    assert result.returncode == (expected if expected == 1 else 0), result.stdout + result.stderr
    if '--collect-only' in options:
        assert 'starting pytest with 1 validated selection(s)' in result.stderr
    else:
        from test_storage import directory
        import json
        base = directory('sessions-host', root=checkout, create=False)
        run = base / json.loads((base / 'current.json').read_text())['run']
        from detached_launcher import lock, busy
        deadline = time.monotonic() + 20
        with lock(run / 'owner') as owner:
            while busy(owner) and time.monotonic() < deadline:
                time.sleep(.05)
            assert not busy(owner), f'Test controller did not finish: {run}'
        assert int((run / 'result').read_text()) == expected
        nested_diagnostics = '\n'.join(path.read_text(errors='replace')[-8192:] for path in
            sorted((checkout / 'output/test-runs/host/reports').glob('*/category-*.log')))
        summary = '1 deselected' if expected == 5 else ('1 passed' if expected == 0 else '1 failed')
        # Admission succeeds independently of the retained test verdict.
        assert summary in nested_diagnostics, nested_diagnostics
    assert 'private_sentinel' not in result.stdout + result.stderr
    assert not list((checkout / 'tests/unit').rglob('*.pyc'))
