"""The category dispatcher must not become an arbitrary root command runner."""
from tests.support.vm_registry import vm_name

from pathlib import Path
from contextlib import nullcontext
import json
import os
import runpy
import shutil
import subprocess
import textwrap
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

runner = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/onpc-test-runner'))
VM_ARGS = ['--vm', vm_name()]
FIXTURE_WRAPPERS = ('check_fixture_provisioning', 'check_fixture_system_product_free',
                    'check_parent_setup', 'check_parent_input', 'check_parent_standard_input')


def select(root, argv):
    return runner['selection'](root, [*argv, *VM_ARGS])


@pytest.fixture
def checkout(tmp_path):
    root = Path(__file__).resolve().parents[2]
    tools = tmp_path / 'tools'
    tools.mkdir()
    for name in ('regression_process.py', 'test_activity.py'):
        shutil.copy2(root / 'tools' / name, tools / name)
    integration = tmp_path / 'tests/integration'
    integration.mkdir(parents=True)
    shutil.copy2(root / 'tests/integration/vm_config.py', integration / 'vm_config.py')
    (tmp_path / 'config').mkdir()
    shutil.copy2(root / 'config/test-vm.json', tmp_path / 'config/test-vm.json')
    (integration / 'check_future_feature.py').touch()
    (integration / 'system_runner.py').touch()
    unit = tmp_path / 'tests/unit'
    unit.mkdir()
    (unit / 'test_future_cleanup_safety.py').touch()
    (unit / 'test_graphical_lease.py').touch()
    return tmp_path


def test_future_check_needs_no_allowlist_change(checkout):
    command = select(checkout, ['integration', 'check_future_feature'])
    assert command == ['/usr/bin/python3', '-B',
                       str(checkout / 'tests/integration/check_future_feature.py')]


@pytest.mark.parametrize('name', ['../check_future_feature', '/tmp/check_other.py',
                                   'graphical_worker', '-c', 'check_x;id'])
def test_rejects_non_category_paths_and_code(checkout, name):
    with pytest.raises((ValueError, SystemExit)):
        select(checkout, ['integration', name])


def test_rejects_extra_arguments(checkout):
    with pytest.raises(ValueError):
        select(checkout, ['integration', 'check_future_feature', '--command', 'id'])


@pytest.fixture
def fixture_selection(checkout):
    from tools.fixture_execution import Selection
    (checkout / 'tests/integration/check_fixture_provisioning.py').touch()
    return Selection('ubuntu', 'a' * 64,
        '/tmp/onpc-native-runtime-ubuntu-' + 'a' * 64 + '-private',
        1, 2, '/tmp/retention-private', 3, 4, 'b' * 32, 'c' * 64).record()


@pytest.mark.parametrize('suffix', ['', '.py'])
@pytest.mark.parametrize('selector', FIXTURE_WRAPPERS)
@pytest.mark.parametrize(('vm', 'target'), [('onpc-Ubuntu26.04', 'ubuntu'), ('onpc-Fedora44', 'fedora')])
def test_fixture_selection_dispatches_only_fixed_wrapper(checkout, fixture_selection, suffix, selector, vm, target):
    (checkout / 'tests/integration' / (selector + '.py')).touch()
    fixture_selection['target'] = target
    fixture_selection['allocation'] = fixture_selection['allocation'].replace('ubuntu', target)
    command = runner['selection'](checkout, ['integration',
        selector + suffix, '--vm', vm,
        '--fixture-selection', json.dumps(fixture_selection)])
    assert command == ['/usr/bin/python3', '-B',
        str(checkout / 'tests/integration' / (selector + '.py')),
        '--fixture-selection', json.dumps(fixture_selection, sort_keys=True)]


@pytest.mark.parametrize('suffix', ['', '.py'])
@pytest.mark.parametrize(('vm', 'target'), [('onpc-Ubuntu26.04', 'ubuntu'), ('onpc-Fedora44', 'fedora')])
def test_installed_system_dispatch_is_bound_to_qualified_target(checkout, fixture_selection, suffix, vm, target):
    name = 'check_fixture_system_installed'
    (checkout / 'tests/integration' / (name + '.py')).touch()
    fixture_selection['target'] = target
    fixture_selection['allocation'] = fixture_selection['allocation'].replace('ubuntu', target)
    command = runner['selection'](checkout, ['integration', name + suffix,
        '--vm', vm, '--fixture-selection', json.dumps(fixture_selection)])
    assert command == ['/usr/bin/python3', '-B',
        str(checkout / 'tests/integration' / (name + '.py')),
        '--fixture-selection', json.dumps(fixture_selection, sort_keys=True)]
    other = 'onpc-Fedora44' if target == 'ubuntu' else 'onpc-Ubuntu26.04'
    with pytest.raises(ValueError, match='fixture-target-not-qualified'):
        runner['selection'](checkout, ['integration', name + suffix,
            '--vm', other, '--fixture-selection', json.dumps(fixture_selection)])


@pytest.mark.parametrize('name', ['check_fixture_e2e_installed', 'check_e2e_approval_flow',
                                  'check_e2e_native_fixtures'])
@pytest.mark.parametrize(('vm', 'target'), [('onpc-Ubuntu26.04', 'ubuntu'), ('onpc-Fedora44', 'fedora')])
def test_installed_e2e_dispatch_is_bound_to_qualified_target(checkout, fixture_selection, name, vm, target):
    (checkout / 'tests/integration' / (name + '.py')).touch()
    fixture_selection['target'] = target
    fixture_selection['allocation'] = fixture_selection['allocation'].replace('ubuntu', target)
    arguments = ['integration', name, '--fixture-selection', json.dumps(fixture_selection)]
    command = runner['selection'](checkout, [*arguments, '--vm', vm])
    assert command[-2:] == ['--fixture-selection', json.dumps(fixture_selection, sort_keys=True)]
    with pytest.raises(ValueError, match='fixture-target-not-qualified'):
        runner['selection'](checkout, [*arguments, '--vm',
            'onpc-Fedora44' if target == 'ubuntu' else 'onpc-Ubuntu26.04'])


@pytest.mark.parametrize('name', ['check_fixture_e2e_product_free',
                                  'check_e2e_product_free_entry', 'check_e2e_package_upgrade'])
@pytest.mark.parametrize(('vm', 'target'), [('onpc-Ubuntu26.04', 'ubuntu'), ('onpc-Fedora44', 'fedora')])
def test_product_free_e2e_dispatch_is_bound_to_qualified_target(checkout, fixture_selection, name, vm, target):
    (checkout / 'tests/integration' / (name + '.py')).touch()
    fixture_selection['target'] = target
    fixture_selection['allocation'] = fixture_selection['allocation'].replace('ubuntu', target)
    arguments = ['integration', name, '--fixture-selection', json.dumps(fixture_selection)]
    command = runner['selection'](checkout, [*arguments, '--vm', vm])
    assert command[-2:] == ['--fixture-selection', json.dumps(fixture_selection, sort_keys=True)]
    with pytest.raises(ValueError, match='fixture-target-not-qualified'):
        runner['selection'](checkout, [*arguments, '--vm',
            'onpc-Fedora44' if target == 'ubuntu' else 'onpc-Ubuntu26.04'])


@pytest.mark.parametrize('options', [
    ['--list'], ['--qualify-install'], ['--qualify-install-refusal'],
])
def test_e2e_fixture_selection_does_not_enable_other_envelopes(fixture_selection, options):
    root = Path(__file__).resolve().parents[2]
    with pytest.raises(ValueError, match='unexpected-fixture-selection'):
        runner['selection'](root, ['e2e', *options, '--vm', 'onpc-Ubuntu26.04',
            '--fixture-selection', json.dumps(fixture_selection)])


def test_transfer_dispatch_is_ubuntu_only_and_preserves_frozen_record(checkout, fixture_selection):
    (checkout / 'tests/integration/check_fixture_transfer.py').touch()
    options = ['--fixture-selection', json.dumps(fixture_selection)]
    command = runner['selection'](checkout, ['integration', 'check_fixture_transfer',
        '--vm', 'onpc-Ubuntu26.04', *options])
    assert command[-2:] == ['--fixture-selection', json.dumps(fixture_selection, sort_keys=True)]
    for suffix in ('', '.py'):
        with pytest.raises(ValueError, match='fixture-target-not-qualified'):
            runner['selection'](checkout, ['integration', 'check_fixture_transfer' + suffix,
                '--vm', 'onpc-Fedora44', *options])


def test_transfer_e2e_dispatch_preserves_selection_without_enabling_install(
        checkout, fixture_selection):
    root = checkout
    e2e = root / 'tests/e2e'
    e2e.mkdir()
    (e2e / 'runner.py').write_text('def preflight(argv, **kwargs):\n    return {}\n')
    artifacts = checkout / 'onpc-transfer-artifacts'
    artifacts.mkdir()
    options = ['--fixture-selection', json.dumps(fixture_selection)]
    command = runner['selection'](root, ['e2e', '--qualify-transfer',
        '--artifacts', str(artifacts), '--vm', 'onpc-Ubuntu26.04', *options])
    assert command[-2:] == ['--fixture-selection', json.dumps(fixture_selection, sort_keys=True)]
    with pytest.raises(ValueError, match='unexpected-fixture-selection'):
        runner['selection'](root, ['e2e', '--qualify-transfer',
            '--artifacts', str(artifacts), '--vm', 'onpc-Fedora44', *options])


@pytest.mark.parametrize('payload', ['{', 'null', '[]', '{}', 'x' * 8193])
def test_fixture_selection_rejects_malformed_json_or_record(checkout, fixture_selection, payload):
    with pytest.raises(ValueError):
        runner['selection'](checkout, ['integration', 'check_fixture_provisioning',
            '--vm', 'onpc-Ubuntu26.04', '--fixture-selection', payload])


@pytest.mark.parametrize(('field', 'value'), [
    ('schema', 'foreign-schema'), ('target', 'other'), ('key', 'not-a-digest'),
    ('allocation', '/tmp/unrelated'), ('journal', '/tmp/unrelated'),
    ('run', 'foreign-run'), ('device', True), ('inode', 0),
    ('journal_device', -1), ('journal_inode', '4'), ('build_identity', 'foreign'),
    ('command', '/bin/sh'),
])
def test_fixture_selection_rejects_foreign_identity(checkout, fixture_selection, field, value):
    fixture_selection[field] = value
    with pytest.raises(ValueError):
        runner['selection'](checkout, ['integration', 'check_fixture_provisioning',
            '--vm', 'onpc-Ubuntu26.04', '--fixture-selection', json.dumps(fixture_selection)])


@pytest.mark.parametrize('args', [
    ['check_future_feature'], ['--list'], ['check_fixture_provisioning', '--list'],
])
@pytest.mark.parametrize('vm', ['onpc-Ubuntu26.04', 'onpc-Fedora44'])
def test_fixture_selection_refuses_other_selector_or_listing(checkout, fixture_selection, args, vm):
    with pytest.raises(ValueError, match='unexpected-fixture-selection'):
        runner['selection'](checkout, ['integration', *args, '--vm', vm,
            '--fixture-selection', json.dumps(fixture_selection)])


@pytest.mark.parametrize(('target', 'vm'), [
    ('fedora', 'onpc-Ubuntu26.04'), ('ubuntu', vm_name(1)),
])
@pytest.mark.parametrize('selector', FIXTURE_WRAPPERS)
def test_fixture_selection_refuses_unqualified_target(checkout, fixture_selection, target, vm, selector):
    fixture_selection['target'] = target
    fixture_selection['allocation'] = '/tmp/onpc-native-runtime-' + target + '-' + 'a' * 64 + '-private'
    with pytest.raises(ValueError, match='fixture-target-not-qualified'):
        runner['selection'](checkout, ['integration', selector,
            '--vm', vm, '--fixture-selection', json.dumps(fixture_selection)])


@pytest.mark.parametrize('category,arguments', [
    *(('integration', [selector]) for selector in FIXTURE_WRAPPERS),
    ('system', ['--artifacts', '/tmp/onpc-current']),
])
def test_fixture_selection_refuses_unknown_vm(checkout, fixture_selection, category, arguments):
    with pytest.raises(ValueError):
        runner['selection'](checkout, [category, *arguments, '--vm', 'unqualified-target',
            '--fixture-selection', json.dumps(fixture_selection)])


@pytest.mark.parametrize(('vm', 'target'), [('onpc-Ubuntu26.04', 'ubuntu'), ('onpc-Fedora44', 'fedora')])
def test_system_fixture_selection_preserves_exact_record(checkout, fixture_selection, vm, target):
    fixture_selection['target'] = target
    fixture_selection['allocation'] = fixture_selection['allocation'].replace('ubuntu', target)
    command = runner['selection'](checkout, ['system', '--vm', vm,
        '--artifacts', '/tmp/onpc-current', '--fixture-selection', json.dumps(fixture_selection)])
    assert command == ['/usr/bin/python3', '-B', str(checkout / 'tests/integration/system_runner.py'),
        '--vm', vm, '--fixture-selection', json.dumps(fixture_selection, sort_keys=True),
        '--artifacts', '/tmp/onpc-current']


def test_rejects_symlink(checkout, tmp_path):
    (checkout / 'tests/integration/check_link.py').symlink_to(tmp_path / 'other.py')
    with pytest.raises(ValueError):
        select(checkout, ['integration', 'check_link'])


def test_system_selector_stays_a_single_argument(checkout):
    value = 'test_example[foo]; echo surprise'
    command = select(checkout, ['system', '--list', '--test', value])
    assert command[-2:] == [f'--test={value}', '--list']


def test_system_update_pins_both_artifact_directories(checkout):
    command = select(checkout, ['system', '--artifacts', '/tmp/onpc-current',
                               '--previous-artifacts', '/var/tmp/onpc-previous',
                               '--area', 'session'])
    assert command[3:] == [*VM_ARGS, '--artifacts', '/tmp/onpc-current',
                           '--previous-artifacts', '/var/tmp/onpc-previous', '--area=session']


def test_system_dispatch_preserves_explicit_fast_policy(checkout):
    args = ['system', '--artifacts', '/tmp/onpc-current']
    strict = select(checkout, args)
    fast = select(checkout, [*args, '--skip-backing-verification'])
    assert fast == [*strict, '--skip-backing-verification']


@pytest.mark.parametrize('path', ['relative', '/etc', '/tmp/unrelated',
                                  '/tmp/onpc-previous/../other'])
def test_system_update_rejects_unconfined_prior_payload(checkout, path):
    with pytest.raises((ValueError, SystemExit)):
        select(checkout, ['system', '--artifacts', '/tmp/onpc-current',
                         '--previous-artifacts', path])


@pytest.mark.parametrize('arguments', [[], ['--artifacts', 'relative'], ['--command', 'id']])
def test_system_rejects_invalid_options(checkout, arguments):
    with pytest.raises(ValueError):
        select(checkout, ['system', *arguments])


@pytest.mark.parametrize('status', [0, 1])
def test_dispatch_runs_only_selected_controller_with_retention_guard(checkout, monkeypatch, status):
    import test_storage
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid: checkout / 'retention')
    guard = Mock()
    monkeypatch.setitem(runner['run'].__globals__, 'retention_guard', guard)
    execute = Mock(return_value=SimpleNamespace(returncode=status))
    monkeypatch.setattr(runner['subprocess'], 'run', execute)
    monkeypatch.setattr(runner['os'], 'getgrouplist', lambda *args: [1000])
    caller = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name='fixture', pw_dir='/tmp')
    assert runner['run'](checkout, ['integration', 'check_future_feature', *VM_ARGS], caller) == status
    execute.assert_called_once()
    assert execute.call_args.args[0] == select(checkout, ['integration', 'check_future_feature'])
    assert 'user' not in execute.call_args.kwargs
    assert guard.call_args_list == [call(checkout), call(checkout)]


@pytest.mark.parametrize('safety_status', [0, 1])
def test_unattended_dispatcher_leaves_checkout_build_cleanable(checkout, safety_status):
    """Exercise interpreter startup -> checkout imports -> real package clean.

    In-process runpy tests inherit pytest's no-bytecode setting and miss the
    installed dispatcher's interpreter flags. Publishing builds also use a fresh
    source snapshot, which omits caches left in the developer's checkout.
    """
    root = Path(__file__).resolve().parents[2]
    tools = checkout / 'tools'
    for name in ('onpc-test-runner', 'regression_process.py', 'test_launcher.py', 'test_activity.py',
                 'test_retention.py', 'test_io.py', 'test_input_transfer.py', 'test_storage.py',
                 'evidence_capture.py', 'evidence_identity.py',
                 'dev_checkout.py', 'install_test_runner.py', 'vm_pool.py'):
        shutil.copy2(root / 'tools' / name, tools / name)
    for relative in ('setup.sh', 'Makefile', 'config/com.puffyslippers.onpc.development.policy'):
        target = checkout / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, target)
    installer = runpy.run_path(str(root / 'tools/install_test_runner.py'))
    rendered = installer['render_helper'](checkout, 'onpc-test-runner', {})
    installed = checkout.parent / 'installed-test-runner'
    installed.write_text(rendered)

    # Use the rendered helper's actual shebang in a fresh process. Only process
    # execution and signal/pipe setup are replaced; selection and the real
    # selected controller command still execute unchanged, without a test gate.
    probe = checkout.parent / 'dispatcher-probe'
    probe.write_text(rendered.splitlines()[0] + '\n' + textwrap.dedent('''\
        from contextlib import nullcontext
        import os
        from pathlib import Path
        import pwd
        import runpy
        import sys
        from unittest.mock import patch

        load = runpy.run_path
        dispatcher = load(sys.argv[1])
        sys.path.insert(0, str(Path(dispatcher['CHECKOUT']) / 'tools'))
        import test_storage
        test_storage.privileged_state = lambda uid: Path(dispatcher['CHECKOUT']) / 'retention'
        dispatcher['run'].__globals__['retention_guard'] = lambda root: None
        calls = []
        safety_status = int(sys.argv[2])

        def execute(self, command, **kwargs):
            calls.append(command)
            return safety_status if len(calls) == 1 else 0

        def load_with_owned_process_stub(path):
            namespace = load(path)
            if Path(path).name == 'regression_process.py':
                namespace['Control'].installed = lambda self, **kwargs: nullcontext(self)
                namespace['Control'].run = execute
            return namespace

        with patch.object(runpy, 'run_path', load_with_owned_process_stub):
            status = dispatcher['run'](
                Path(dispatcher['CHECKOUT']),
                ['--unattended', 'system', '--artifacts', '/tmp/onpc-build-regression',
                 '--vm', sys.argv[3]],
                pwd.getpwuid(os.getuid()))
        assert status == safety_status
        assert len(calls) == 1
        assert calls[0][2].endswith('/tests/integration/system_runner.py')
        assert '--cleanup-prerequisites' not in calls[0]
        print('dispatcher checkout imports exercised')
        '''))
    probe.chmod(0o755)
    environment = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8',
                   'PYTHONDONTWRITEBYTECODE': '1'}
    result = subprocess.run([str(probe), str(installed), str(safety_status), vm_name()],
                            cwd=checkout, env=environment, capture_output=True,
                            text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'dispatcher checkout imports exercised' in result.stdout

    debian = checkout / 'debian'
    debian.mkdir()
    for name in ('rules', 'control', 'changelog'):
        shutil.copy2(root / 'debian' / name, debian / name)
    caches = list(tools.rglob('__pycache__'))
    # Model the caller's inability to unlink files in a root-owned cache without
    # requiring root or leaving privileged artifacts in the real checkout.
    for cache in caches:
        cache.chmod(0o555)
    try:
        clean = subprocess.run(['/usr/bin/make', '-f', 'debian/rules', 'clean'],
                               cwd=checkout, env=environment, capture_output=True,
                               text=True, timeout=30, check=False)
        assert clean.returncode == 0, clean.stdout + clean.stderr
        assert not caches, 'the dispatcher must not write bytecode into the checkout'
    finally:
        for cache in caches:
            if cache.exists():
                cache.chmod(0o755)


@pytest.mark.parametrize('unattended', [False, True])
@pytest.mark.parametrize('name', ['check_test_recovery', 'check_graphical_recovery',
                                  'check_system_recovery'])
def test_recovery_dispatch_preserves_unfinished_vm_journal(checkout, monkeypatch, name, unattended):
    import test_storage
    (checkout / 'tests/integration' / (name + '.py')).touch()
    state = checkout / 'retention'
    state.mkdir(mode=0o700)
    journal = state / 'current.json'
    journal.write_text(json.dumps(dict(run='1' * 32, finished=False, paths=[], history=[])))
    journal.chmod(0o600)
    before = journal.read_bytes()
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid: state)
    guard = Mock(side_effect=ValueError('unfinished VM recovery'))
    monkeypatch.setitem(runner['run'].__globals__, 'retention_guard', guard)
    execute = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(runner['subprocess'], 'run', execute)
    monkeypatch.setattr(runner['os'], 'getgrouplist', lambda *args: [1000])
    control = SimpleNamespace(run=Mock(return_value=0))
    control.installed = lambda **kwargs: nullcontext(control)
    monkeypatch.setattr(runner['runpy'], 'run_path', lambda path: {
        'Control': lambda: control, 'safety_command': lambda root: ['cleanup-prerequisites']})
    caller = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name='fixture', pw_dir=str(checkout))
    arguments = ['integration', name, *VM_ARGS]
    assert runner['run'](checkout, (['--unattended'] if unattended else []) + arguments, caller) == 0
    calls = (control.run if unattended else execute).call_args_list
    assert len(calls) == 1
    assert 'user' not in calls[0].kwargs
    assert calls[0].kwargs['env']['PKEXEC_UID'] == '1000'
    assert calls[0].args[0][-1] == str(checkout / 'tests/integration' / (name + '.py'))
    guard.assert_not_called()
    assert journal.read_bytes() == before


@pytest.mark.parametrize('unattended', [False, True])
@pytest.mark.parametrize('arguments', [
    ['system', '--artifacts', '/tmp/onpc-selected', '--area', 'session'],
    ['integration', 'check_graphical_smoke'], ['integration', 'check_e2e_watch.py'],
])
def test_selected_producer_dispatch_keeps_command_without_parent_owner(
        checkout, monkeypatch, unattended, arguments):
    import test_retention
    for name in ('check_graphical_smoke.py', 'check_e2e_watch.py'):
        (checkout / 'tests/integration' / name).touch()
    owner = Mock(side_effect=AssertionError('dispatcher opened a producer owner'))
    monkeypatch.setattr(test_retention.Store, 'session', owner)
    inherited = Mock(side_effect=AssertionError('dispatcher forwarded producer authority'))
    monkeypatch.setattr(test_retention, 'environment', inherited)
    execute = Mock(return_value=SimpleNamespace(returncode=7))
    monkeypatch.setattr(runner['subprocess'], 'run', execute)
    control = SimpleNamespace(run=Mock(return_value=7))
    control.installed = Mock(return_value=nullcontext(control))
    monkeypatch.setattr(runner['runpy'], 'run_path', lambda path: {'Control': lambda: control})
    caller = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name='fixture', pw_dir=str(checkout))
    selected = [*arguments, *VM_ARGS]
    expected = runner['selection'](checkout, selected)
    assert runner['run'](checkout, (['--unattended'] if unattended else []) + selected, caller) == 7
    invocation = (control.run if unattended else execute).call_args
    assert invocation.args == (expected,)
    assert invocation.kwargs['cwd'] == checkout
    assert invocation.kwargs['env']['PKEXEC_UID'] == '1000'
    assert not {'ONPC_TEST_RETENTION', 'ONPC_TEST_RETENTION_FD',
                'ONPC_QUALIFICATION_RETENTION_RUN'} & invocation.kwargs['env'].keys()
    if unattended:
        control.installed.assert_called_once_with(pipe=True)
    else:
        from test_storage import scratch_descriptors
        assert invocation.kwargs['pass_fds'] == scratch_descriptors()
    owner.assert_not_called()
    inherited.assert_not_called()


@pytest.mark.parametrize('unattended', [False, True])
@pytest.mark.parametrize('mode', ['execution-preflight', 'asset-transfer-qualification'])
def test_e2e_child_owns_capture_across_real_subprocess_boundary(
        checkout, monkeypatch, unattended, mode):
    """Use the real entry point, session and mint; double only guest dispatch."""
    from tools import test_retention as retention, test_storage as storage
    root = Path(__file__).resolve().parents[2]
    e2e = checkout / 'tests/e2e'
    e2e.mkdir()
    child = e2e / 'runner.py'
    child.write_text(textwrap.dedent('''\
        def preflight(argv, **kwargs):
            return dict(mode=MODE_LITERAL, artifacts='/tmp/onpc-selected', cases=[],
                        fixture_selection={'frozen': True})
        if __name__ != '__main__':
            # Declaration preflight must not initialize any producer machinery.
            pass
        else:
            exec(CHILD_LITERAL)
        ''').replace('MODE_LITERAL', repr(mode)).replace('CHILD_LITERAL', repr(textwrap.dedent('''\
        import json, os, runpy, sys
        from pathlib import Path
        from types import SimpleNamespace
        SOURCE = Path(SOURCE_LITERAL)
        CHECKOUT = Path(__file__).resolve().parents[2]
        sys.path[:0] = [str(SOURCE), str(SOURCE / 'tests/integration')]
        from tools import evidence_capture as capture, test_retention as retention, test_storage as storage
        import qualification_storage
        storage.ROOT = CHECKOUT
        storage.BASE = CHECKOUT / 'output/test-runs'
        journal = storage.directory('state') / 'retention-selected-child'
        storage.privileged_state = lambda uid: journal
        capture._authenticated_caller = lambda: dict(uid=os.geteuid(), gid=os.getegid())
        def mint(store):
            return capture.issue_session(store, repository=CHECKOUT,
                workflow='child-owner-fixture', task='E06a', check='selected-child',
                inputs_sha256='a' * 64, sources_sha256='b' * 64,
                consumers={'c' * 64: dict(consumer_id='c' * 64, revision_sha256='d' * 64)})
        if sys.argv[1:] == ['--inherited-only']:
            inherited = retention.Store(json.loads(os.environ[retention.VARIABLE])[0])
            try:
                mint(inherited)
            except ValueError as error:
                assert 'live producer session' in str(error)
                print('inherited-only refused')
                raise SystemExit(0)
            raise AssertionError('inherited authority minted a capture')
        if __name__ == '__main__':
            assert retention.VARIABLE not in os.environ
            assert retention.OWNER_VARIABLE not in os.environ
            qualification_storage.ROOT = CHECKOUT
            qualification_storage.os = SimpleNamespace(**{**vars(os), 'geteuid': lambda: 0})
            qualification_storage.recover_pending = lambda *args: None
            load = qualification_storage.runpy.run_path
            qualification_storage.runpy.run_path = lambda path: (
                {'retention_guard': lambda root: None} if Path(path).name == 'onpc-test-runner'
                else load(path))
            def execute(*args, **kwargs):
                store = retention.Store(journal)
                binding = store.producer_binding()
                context = capture.session_context(mint(store))
                assert context['run'] == binding[3]
                requested = os.environ.get('ONPC_QUALIFICATION_RETENTION_RUN')
                assert requested is None or context['run'] == requested
                print('child live owner ' + context['run'])
                return 7
            sys.modules['execution'] = SimpleNamespace(main=execute)
            sys.modules['check_graphical_smoke'] = SimpleNamespace(main=execute)
            namespace = load(str(SOURCE / 'tests/e2e/runner.py'))
            namespace['main'].__globals__['preflight'] = preflight
            raise SystemExit(namespace['main']())
        ''').replace('SOURCE_LITERAL', repr(str(root))))))
    monkeypatch.setattr(storage, 'ROOT', checkout)
    monkeypatch.setattr(storage, 'BASE', checkout / 'output/test-runs')
    monkeypatch.delenv(retention.VARIABLE, raising=False)
    monkeypatch.delenv(retention.OWNER_VARIABLE, raising=False)
    monkeypatch.delenv('ONPC_QUALIFICATION_RETENTION_RUN', raising=False)
    original_run = subprocess.run
    # Deliberately pass a real parent's environment and descriptor to a fresh
    # interpreter: this transfers coordination, never minting authority.
    parent = retention.Store(storage.directory('state') / 'retention-parent-fixture')
    with parent.session():
        before = (parent.path / 'current.json').read_bytes()
        inherited = original_run(['/usr/bin/python3', '-B', str(child), '--inherited-only'],
            env={**os.environ, **retention.environment()},
            pass_fds=(int(os.environ[retention.OWNER_VARIABLE]),),
            capture_output=True, text=True, timeout=15, check=False)
        assert inherited.returncode == 0, inherited.stdout + inherited.stderr
        assert inherited.stdout.strip() == 'inherited-only refused'
        assert (parent.path / 'current.json').read_bytes() == before
    expected_run = 'e' * 32
    journal = storage.directory('state') / 'retention-selected-child'
    if unattended:
        with retention.Store(journal).session(run=expected_run):
            pass
    output = []
    invocations = []
    def execute(command, **kwargs):
        invocations.append((command, kwargs))
        result = original_run(command, **kwargs, capture_output=True, text=True, timeout=15)
        output.append(result.stdout + result.stderr)
        return result
    monkeypatch.setattr(runner['subprocess'], 'run', execute)
    load = runpy.run_path
    controls = []
    def modules(path):
        module = load(path)
        if Path(path).name == 'regression_process.py':
            control = module['Control']()
            control.installed = Mock(return_value=nullcontext(control))
            run = control.run
            def controlled(command, **kwargs):
                invocations.append((command, kwargs))
                return run(command, **kwargs, output=lambda data: output.append(data.decode()), timeout=15)
            control.run = controlled
            controls.append(control)
            return {'Control': lambda: control}
        return module
    monkeypatch.setattr(runner['runpy'], 'run_path', modules)
    selection = ['e2e', '--artifacts', '/tmp/onpc-selected',
                 '--qualify-transfer' if mode == 'asset-transfer-qualification' else '--ready', *VM_ARGS]
    command = runner['selection'](checkout, selection)
    caller = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name='fixture', pw_dir=str(checkout))
    arguments = ([f'--retention-run={expected_run}', '--unattended'] if unattended else []) + selection
    assert runner['run'](checkout, arguments, caller) == 7, ''.join(output)
    assert len(invocations) == 1 and invocations[0][0] == command
    assert 'child live owner ' in ''.join(output)
    state = json.loads((journal / 'current.json').read_text())
    assert state['finished'] is True
    if unattended:
        assert state['run'] == expected_run and state['history'] == []
        controls[0].installed.assert_called_once_with(pipe=True)
    assert not {'ONPC_TEST_RETENTION', 'ONPC_TEST_RETENTION_FD'} & invocations[0][1]['env'].keys()
    assert retention.VARIABLE not in os.environ and retention.OWNER_VARIABLE not in os.environ
    assert 'ONPC_QUALIFICATION_RETENTION_RUN' not in os.environ
