"""Boundary and execution tests for all approved test category routes."""
from tools.test_storage import named_input
from tests.support.vm_registry import vm_name
from dataclasses import replace
from contextlib import nullcontext
import json
import os
import runpy
import subprocess
import sys
from unittest.mock import Mock
from types import SimpleNamespace

import pytest

from tests.support.paths import ROOT
from tests.support.launcher import synthetic_package_identity
import test_launcher as host
import test_commands as commands

VM_ARGS = ['--vm', vm_name()]
SYSTEM_BOOTSTRAP_ALIASES = ('check_parent_setup', 'check_parent_input',
                            'check_parent_standard_input')
PRODUCT_FREE_FIXTURE_SELECTORS = ('check_fixture_system_product_free',
                                 *SYSTEM_BOOTSTRAP_ALIASES)


@pytest.mark.parametrize('name,options,target,suffix,build_status', [
    ('check_e2e_gdm_recipient', {}, vm_name(0), '', 0),
    ('check_e2e_feedback_read', {'package_source': True}, vm_name(1), '.py', 7),
    ('check_e2e_read_overlay_about_and_links', {'fixture_source': True}, vm_name(1), '.py', 0),
    ('check_e2e_upgrade_assets', {'upgrade_source': True}, vm_name(0), '', 7),
    ('check_e2e_kiosk_eligible_choices', {'vm_source': True, 'fixture_source': True},
     vm_name(0), '', 0),
    ('check_fixture_system_installed', {'vm_source': True, 'fixture_source': True},
     vm_name(1), '.py', 0),
])
def test_named_input_preparation_precedes_dispatch_and_failure_stops_privilege(
        monkeypatch, synthetic_package_identity, name, options, suffix, build_status, target):
    import dev_privileges
    import regression_process
    import test_storage

    monkeypatch.setenv('ONPC_TEST_VM', target)
    vm_args = ['--vm', target]
    output = str(test_storage.named_input(**options))
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    allocate = Mock(return_value=output)
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    fixture_options = (['--fixture-selection', '{"frozen":"fixture"}']
                       if name in ('check_fixture_provisioning', 'check_fixture_system_installed',
                                   *PRODUCT_FREE_FIXTURE_SELECTORS,
                                   *commands.INSTALLED_E2E_FIXTURE_SELECTORS,
                                   'check_fixture_transfer', 'check_fixture_serial',
                                   'check_fixture_recorded_serial') else [])
    freeze = Mock(return_value=fixture_options)
    monkeypatch.setattr(commands, 'qualification_fixture_options', freeze)
    execute = Mock(side_effect=[build_status, 0])
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    authorize = Mock()
    monkeypatch.setattr(dev_privileges, 'check', authorize)
    selector = name + suffix
    assert regression_process.category_run(
        ROOT, 'integration', [selector], pipe=False) == build_status
    allocate.assert_called_once_with(output)
    flags = ['--upgrade-inputs'] if options.get('upgrade_source') else []
    assert execute.call_args_list[0].args[0] == commands.python_file(
        ROOT, 'tools/vm_artifacts.py', *flags, '--output', output, *vm_args)
    if build_status:
        assert execute.call_count == 1
        authorize.assert_not_called()
        freeze.assert_not_called()
    else:
        assert execute.call_count == 2
        authorize.assert_called_once_with('/usr/local/libexec/onpc-test-runner')
        assert freeze.call_count == 1
        assert freeze.call_args.args == (ROOT, 'integration', [selector])
        assert isinstance(freeze.call_args.kwargs['control'], regression_process.Control)
        assert freeze.call_args.kwargs['environment']['PYTHONUNBUFFERED'] == '1'
        assert execute.call_args.args[0] == [
            '/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
            '/usr/local/libexec/onpc-test-runner', '--unattended', 'integration', selector, *vm_args,
            *fixture_options]


def test_fixture_qualification_refuses_other_target_before_preparing(monkeypatch):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name='unqualified-target'))
    control = Mock()
    with pytest.raises(ValueError, match='target is unavailable'):
        commands.qualification_fixture_options(ROOT, 'integration', ['check_fixture_provisioning'], control=control)
    control.run.assert_not_called()


@pytest.mark.parametrize(('category', 'arguments'), [
    ('integration', ['check_fixture_transfer']),
    ('integration', ['check_fixture_transfer.py']),
    ('e2e', ['--qualify-transfer']),
])
@pytest.mark.parametrize(('vm', 'target'), [(vm_name(0), 'ubuntu'), (vm_name(1), 'fedora')])
def test_transfer_freezes_exact_input_before_privileged_dispatch(
        monkeypatch, frozen_fixture_selection, category, arguments, vm, target):
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    families = json.loads((ROOT / 'config/test-vm.json').read_text())['families']
    fixture_path = next(family['fixture_path'] for family in families
                        if any(entry['name'] == vm for entry in family['vms']))
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    record = frozen_fixture_selection.record()
    def execute(command, **options):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py',
                                               '--target', target, '--fixture-path', fixture_path)
        options['output'](('fixture-execution: selection=' + json.dumps(record) + '\n').encode())
        return 0
    assert commands.qualification_fixture_options(ROOT, category, arguments,
        control=SimpleNamespace(run=execute), environment={}) == [
            '--fixture-selection', json.dumps(record, sort_keys=True)]
    assert commands.qualification_input_options(ROOT, 'check_fixture_transfer') == {
        'vm_source': True, 'fixture_source': True}


@pytest.mark.parametrize(('category', 'arguments'), [
    ('integration', ['check_fixture_transfer']), ('e2e', ['--qualify-transfer']),
])
def test_transfer_refuses_unqualified_target_before_input_preparation(monkeypatch, category, arguments):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name='unqualified-target'))
    control = Mock()
    with pytest.raises(ValueError, match='fixture transfer target is unavailable'):
        commands.qualification_fixture_options(ROOT, category, arguments, control=control)
    if category == 'integration':
        with pytest.raises(ValueError, match='fixture transfer target is unavailable'):
            commands.qualification_artifact_command(ROOT, category, arguments)
    control.run.assert_not_called()


@pytest.mark.parametrize(('category', 'arguments'), [
    ('integration', ['check_graphical_serial']),
    ('integration', ['check_graphical_serial.py']),
    ('integration', ['check_fixture_serial']),
    ('integration', ['check_fixture_serial.py']),
    ('e2e', ['--qualify-install']), ('e2e', ['--qualify-install-refusal']),
])
@pytest.mark.parametrize(('vm', 'target'), [(vm_name(0), 'ubuntu'), (vm_name(1), 'fedora')])
def test_serial_freezes_exact_input_and_refuses_unknown_target_before_preparation(
        monkeypatch, frozen_fixture_selection, category, arguments, vm, target):
    families = json.loads((ROOT / 'config/test-vm.json').read_text())['families']
    fixture_path = next(family['fixture_path'] for family in families
                        if any(entry['name'] == vm for entry in family['vms']))
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    record = frozen_fixture_selection.record()
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    def execute(command, **options):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py',
                                               '--target', target, '--fixture-path', fixture_path)
        options['output'](('fixture-execution: selection=' + json.dumps(record) + '\n').encode())
        return 0
    assert commands.qualification_fixture_options(ROOT, category, arguments,
        control=SimpleNamespace(run=execute), environment={}) == [
            '--fixture-selection', json.dumps(record, sort_keys=True)]
    if category == 'integration':
        # Bare serial needs no assets; qualification retains its readback witness.
        expected = ({'vm_source': True, 'fixture_source': True}
                    if arguments[0].removesuffix('.py') == 'check_fixture_serial' else None)
        assert commands.qualification_input_options(ROOT, arguments[0]) == expected
        if expected is None:
            assert commands.qualification_artifact_command(ROOT, category, arguments) is None
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name='unqualified-target'))
    control = Mock()
    with pytest.raises(ValueError, match='fixture serial target is unavailable'):
        commands.qualification_fixture_options(ROOT, category, arguments, control=control)
    if category == 'integration':
        with pytest.raises(ValueError, match='fixture serial target is unavailable'):
            commands.qualification_artifact_command(ROOT, category, arguments)
    control.run.assert_not_called()


@pytest.mark.parametrize('suffix', ['', '.py'])
@pytest.mark.parametrize(('vm', 'target'), [(vm_name(0), 'ubuntu'), (vm_name(1), 'fedora')])
def test_recorded_serial_freezes_exact_input_before_dispatch(
        monkeypatch, frozen_fixture_selection, suffix, vm, target):
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    families = json.loads((ROOT / 'config/test-vm.json').read_text())['families']
    fixture_path = next(family['fixture_path'] for family in families
                        if any(entry['name'] == vm for entry in family['vms']))
    selector = 'check_fixture_recorded_serial' + suffix
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    record = frozen_fixture_selection.record()
    def execute(command, **options):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py',
                                               '--target', target, '--fixture-path', fixture_path)
        options['output'](('fixture-execution: selection=' + json.dumps(record) + '\n').encode())
        return 0
    assert commands.qualification_fixture_options(ROOT, 'integration', [selector],
        control=SimpleNamespace(run=execute), environment={}) == [
            '--fixture-selection', json.dumps(record, sort_keys=True)]
    assert commands.qualification_input_options(ROOT, selector) == {
        'vm_source': True, 'fixture_source': True}


@pytest.mark.parametrize('suffix', ['', '.py'])
def test_recorded_serial_refuses_before_input_preparation(monkeypatch, suffix):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name='unqualified-target'))
    selector = 'check_fixture_recorded_serial' + suffix
    control = Mock()
    for operation in (
            lambda: commands.plan(ROOT, 'integration', [selector]),
            lambda: commands.qualification_artifact_command(ROOT, 'integration', [selector]),
            lambda: commands.qualification_fixture_options(
                ROOT, 'integration', [selector], control=control)):
        with pytest.raises(ValueError, match='fixture recorded serial target is unavailable'):
            operation()
    control.run.assert_not_called()


@pytest.mark.parametrize('selector', PRODUCT_FREE_FIXTURE_SELECTORS)
@pytest.mark.parametrize('suffix', ['', '.py'])
def test_product_free_fixture_target_refuses_before_package_or_fixture_input(monkeypatch, selector, suffix):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name='unqualified-target'))
    control = Mock()
    for operation in (
            lambda: commands.plan(ROOT, 'integration', [selector + suffix]),
            lambda: commands.qualification_artifact_command(ROOT, 'integration', [selector + suffix]),
            lambda: commands.qualification_fixture_options(
                ROOT, 'integration', [selector + suffix], control=control)):
        with pytest.raises(ValueError, match='target is unavailable'):
            operation()
    control.run.assert_not_called()


@pytest.mark.parametrize(('category', 'arguments'), [
    *(('integration', [name]) for name in PRODUCT_FREE_FIXTURE_SELECTORS),
    ('system', ['--area=lifecycle', '--test=first-configure', '--previous-artifacts=/tmp/onpc-previous']),
])
@pytest.mark.parametrize(('vm', 'target'), [(vm_name(0), 'ubuntu'), (vm_name(1), 'fedora')])
def test_product_free_runner_freezes_exact_input_before_dispatch(
        monkeypatch, category, arguments, frozen_fixture_selection, vm, target):
    import vm_selection
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    fixture_path = vm_selection.selected().fixture_path
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    record = frozen_fixture_selection.record()
    source_edit = arguments == ['check_fixture_system_product_free']
    source = source_proof_selection(frozen_fixture_selection)
    def execute(command, **options):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py', '--target', target,
                                               '--fixture-path', fixture_path,
                                               *(['--qualify-source-edit'] if source_edit else []))
        options['output'](('fixture-execution: selection=' + json.dumps(record) + '\n').encode())
        if source_edit:
            options['output'](('fixture-execution: source-edit=' + json.dumps(source) + '\n').encode())
        return 0
    control = SimpleNamespace(run=Mock(side_effect=execute))
    original = list(arguments)
    assert commands.qualification_fixture_options(ROOT, category, arguments,
        control=control, environment={}) == [
            '--fixture-selection', json.dumps(record, sort_keys=True),
            *(['--fixture-source-selection', json.dumps(source, sort_keys=True)] if source_edit else [])]
    assert arguments == original
    control.run.assert_called_once()


@pytest.mark.parametrize(('category', 'arguments'), [
    *(('integration', [name]) for name in PRODUCT_FREE_FIXTURE_SELECTORS),
    ('system', ['--artifacts=/tmp/onpc-packages', '--previous-artifacts=/tmp/onpc-previous',
                '--area=lifecycle', '--test=first-configure']),
])
@pytest.mark.parametrize('suffix', ['', '.py'])
@pytest.mark.parametrize(('vm', 'target'), [(vm_name(0), 'ubuntu'), (vm_name(1), 'fedora')])
def test_product_free_dispatcher_preserves_the_frozen_record(
        monkeypatch, category, arguments, frozen_fixture_selection, suffix, vm, target):
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    dispatch = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['selection']
    record = frozen_fixture_selection.record()
    encoded = json.dumps(record)
    source_options = (['--fixture-source-selection', json.dumps(source_proof_selection(frozen_fixture_selection))]
                      if arguments == ['check_fixture_system_product_free'] else [])
    selected_arguments = ([arguments[0] + suffix] if category == 'integration' else arguments)
    command = dispatch(ROOT, [category, *selected_arguments, '--fixture-selection', encoded,
                              *source_options, '--vm', vm])
    index = command.index('--fixture-selection')
    assert json.loads(command[index + 1]) == record
    if source_options:
        assert json.loads(command[command.index('--fixture-source-selection') + 1]) == source_proof_selection(frozen_fixture_selection)
    if category == 'system':
        assert command[-2:] == ['--area=lifecycle', '--test=first-configure']
        for option in ('--artifacts', '--previous-artifacts'):
            assert command[command.index(option) + 1] in ('/tmp/onpc-packages', '/tmp/onpc-previous')


@pytest.mark.parametrize('selector', ['check_fixture_provisioning', *SYSTEM_BOOTSTRAP_ALIASES, 'check_future_feature'])
@pytest.mark.parametrize('vm', [vm_name(0), vm_name(1)])
def test_source_proof_option_refuses_other_integration_selectors(monkeypatch, selector, frozen_fixture_selection, vm):
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    dispatch = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['selection']
    with pytest.raises(ValueError, match='unexpected-fixture-source-selection'):
        dispatch(ROOT, ['integration', selector, '--vm', vm,
                        '--fixture-selection', json.dumps(frozen_fixture_selection.record()),
                        '--fixture-source-selection', json.dumps(source_proof_selection(frozen_fixture_selection))])


@pytest.mark.parametrize('suffix', ['', '.py'])
@pytest.mark.parametrize(('vm', 'target'), [(vm_name(0), 'ubuntu'), (vm_name(1), 'fedora')])
def test_installed_system_freezes_original_input_and_actual_source_proof(
        monkeypatch, frozen_fixture_selection, suffix, vm, target):
    import vm_selection
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    fixture_path = vm_selection.selected().fixture_path
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    record = frozen_fixture_selection.record()
    source = source_proof_selection(frozen_fixture_selection)
    def execute(command, **options):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py',
            '--target', target, '--fixture-path', fixture_path, '--qualify-source-edit')
        options['output'](('fixture-execution: selection=' + json.dumps(record) + '\n'
            + 'fixture-execution: source-edit=' + json.dumps(source) + '\n').encode())
        return 0
    control = SimpleNamespace(run=Mock(side_effect=execute))
    options = commands.qualification_fixture_options(ROOT, 'integration',
        ['check_fixture_system_installed' + suffix], control=control, environment={})
    assert options == ['--fixture-selection', json.dumps(record, sort_keys=True),
                       '--fixture-source-selection', json.dumps(source, sort_keys=True)]
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    dispatch = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['selection']
    command = dispatch(ROOT, ['integration', 'check_fixture_system_installed' + suffix,
                              '--vm', vm, *options])
    assert command[3:] == options


@pytest.mark.parametrize('vm', ['unqualified-target'])
@pytest.mark.parametrize('suffix', ['', '.py'])
def test_installed_system_target_refuses_before_any_input(monkeypatch, vm, suffix):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name=vm))
    selector = 'check_fixture_system_installed' + suffix
    control = Mock()
    for operation in (
            lambda: commands.plan(ROOT, 'integration', [selector]),
            lambda: commands.qualification_artifact_command(ROOT, 'integration', [selector]),
            lambda: commands.qualification_fixture_options(
                ROOT, 'integration', [selector], control=control)):
        with pytest.raises(ValueError, match='target is unavailable'):
            operation()
    control.run.assert_not_called()


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'foreign-input', 'oversized', 'malformed'])
@pytest.mark.parametrize(('vm', 'target'), [(vm_name(0), 'ubuntu'), (vm_name(1), 'fedora')])
def test_source_proof_handoff_requires_one_bound_record(monkeypatch, fault, frozen_fixture_selection, vm, target):
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    record = frozen_fixture_selection.record()
    source = source_proof_selection(frozen_fixture_selection)
    if fault == 'foreign-input':
        source['build_identity'] = 'f' * 64
    line = b'fixture-execution: source-edit=' + json.dumps(source).encode() + b'\n'
    line = {'missing': b'', 'duplicate': line * 2,
            'oversized': b'fixture-execution: source-edit=' + b'x' * 8193 + b'\n',
            'malformed': b'fixture-execution: source-edit={\n'}.get(fault, line)
    def execute(command, **options):
        options['output'](b'fixture-execution: selection=' + json.dumps(record).encode() + b'\n' + line)
        return 0
    with pytest.raises(ValueError):
        commands.qualification_fixture_options(ROOT, 'integration', ['check_fixture_system_product_free'],
            control=SimpleNamespace(run=execute), environment={})


@pytest.mark.parametrize('category,arguments', [
    *(('integration', [name]) for name in PRODUCT_FREE_FIXTURE_SELECTORS),
    ('system', ['--artifacts=/tmp/onpc-packages']),
])
@pytest.mark.parametrize(('vm', 'target'), [(vm_name(0), 'fedora'), (vm_name(1), 'ubuntu')])
def test_dispatcher_refuses_foreign_product_free_fixture_target(
        monkeypatch, category, arguments, frozen_fixture_selection, vm, target):
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    frozen_fixture_selection = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    dispatch = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['selection']
    with pytest.raises(ValueError, match='fixture-target-not-qualified'):
        dispatch(ROOT, [category, *arguments, '--fixture-selection',
                        json.dumps(frozen_fixture_selection.record()), '--vm', vm])


@pytest.fixture
def frozen_fixture_selection():
    from tools import fixture_execution
    return fixture_execution.Selection('ubuntu', 'a' * 64,
        '/tmp/onpc-native-runtime-ubuntu-' + 'a' * 64 + '-private',
        1, 2, '/tmp/retention-private', 3, 4, 'b' * 32, 'c' * 64)


def source_proof_selection(selected):
    return selected.record() | {'allocation': '/tmp/onpc-fixture-source-edit-private',
                                'device': 5, 'inode': 6}


@pytest.mark.parametrize(('action', 'status'), [('start', 0), ('start', 7), ('sync-fixtures', 0)])
@pytest.mark.parametrize(('vm', 'target'), [(vm_name(0), 'ubuntu'), (vm_name(1), 'fedora')])
def test_public_fixture_maintenance_keeps_one_selector_and_pins_sync_input(
        monkeypatch, frozen_fixture_selection, action, status, vm, target):
    from contextlib import contextmanager
    import dev_privileges
    import fixture_execution
    import test_retention
    import test_storage
    import vm_pool
    monkeypatch.setattr(dev_privileges, 'check', Mock())
    reserved = []
    @contextmanager
    def reservation(name):
        assert name == vm and not reserved
        reserved.append(name)
        try:
            yield
        finally:
            assert not active
            reserved.pop()
    monkeypatch.setattr(vm_pool, 'reservation', reservation)
    def checkout_arguments():
        assert reserved == [vm]
        return ['--vm-checkout=receipt']
    monkeypatch.setattr(vm_pool, 'arguments', checkout_arguments)
    monkeypatch.setattr(test_storage, 'directory', lambda kind: ROOT / 'unused-state')
    active = []
    sessions = []
    @contextmanager
    def session(**kwargs):
        assert reserved == [vm]
        sessions.append(kwargs)
        active.append(True)
        try:
            yield
        finally:
            active.pop()
    @contextmanager
    def opened():
        assert reserved == [vm]
        yield 12
    store = SimpleNamespace(session=session, opened=opened,
                            read=lambda fd: {'run': 'b' * 32})
    def make_store(path):
        assert reserved == [vm]
        return store
    monkeypatch.setattr(test_retention, 'Store', make_store)
    def prepare(**kwargs):
        assert active and kwargs == {'target': target}
        return frozen_fixture_selection
    monkeypatch.setattr(fixture_execution, 'prepare', prepare)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        assert command.count('--vm') == 1
        assert command[3] == '--vm-checkout=receipt'
        assert bool(active) == (action == 'sync-fixtures')
        return SimpleNamespace(returncode=status)
    monkeypatch.setattr(subprocess, 'run', run)
    function = runpy.run_path(str(ROOT / 'tools/test-vm'))['fixture_maintenance']
    options = ['start', '--fixture-maintenance'] if action == 'start' else [action]
    assert function(options, SimpleNamespace(name=vm)) == status
    assert len(calls) == 1
    assert not reserved
    assert sessions == ([{}] if action == 'start' and status == 0 else
                        [{'run': 'b' * 32}] if action == 'sync-fixtures' else [])


@pytest.mark.parametrize('failure', [None, 'retain-a', 'build-b', 'replace-b'])
@pytest.mark.parametrize(('vm', 'target'), [(vm_name(0), 'ubuntu'), (vm_name(1), 'fedora')])
def test_live_refresh_orders_actual_a_use_before_b_build_and_recovers_failures(
        monkeypatch, frozen_fixture_selection, failure, vm, target):
    import dev_privileges
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    monkeypatch.setattr(dev_privileges, 'check', Mock())
    original = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('runtime-ubuntu-', 'runtime-' + target + '-'))
    replacement = replace(original, key='d' * 64, build_identity='e' * 64,
        allocation=original.allocation.replace('a' * 64, 'd' * 64))
    source = source_proof_selection(original)
    events = []

    def run(command, **kwargs):
        if '--live-refresh-source' in command:
            assert command[command.index('--target') + 1] == target
            events.append('build-a')
            kwargs['output'](b'fixture-execution: selection=' + json.dumps(original.record()).encode() + b'\n')
            kwargs['output'](b'fixture-execution: source-edit=' + json.dumps(source).encode() + b'\n')
        elif '--live-refresh-selection' in command:
            assert command[command.index('--target') + 1] == target
            assert events == ['build-a', 'retain-a']
            events.append('build-b')
            if failure == 'build-b':
                return 7
            kwargs['output'](b'fixture-execution: selection=' + json.dumps(replacement.record()).encode() + b'\n')
        elif command[-1] == 'retain-a':
            events.append('retain-a')
            if failure == 'retain-a':
                return 8
        else:
            events.append('replace-b')
            assert json.loads(command[command.index('--fixture-replacement-selection') + 1]) == replacement.record()
            if failure == 'replace-b':
                return 9
        return 0

    cleanup = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(commands.subprocess, 'run', cleanup)
    control = SimpleNamespace(run=run)
    command = ['/usr/bin/pkexec', '/usr/local/libexec/onpc-test-runner',
               'integration', 'check_fixture_live_refresh', '--vm', vm]
    if failure == 'build-b':
        with pytest.raises(ValueError, match='preparation failed'):
            commands.run_live_refresh(ROOT, command, control=control, environment={})
    else:
        assert commands.run_live_refresh(ROOT, command, control=control, environment={}) == (
            8 if failure == 'retain-a' else 9 if failure else 0)
    assert events[:2] == ['build-a', 'retain-a']
    if failure != 'retain-a':
        assert events[:3] == ['build-a', 'retain-a', 'build-b']
    assert cleanup.call_count == (1 if failure in ('build-b', 'replace-b') else 0)
    if failure in ('build-b', 'replace-b'):
        assert cleanup.call_args.args[0][-4:] == ['vm', '--vm', vm, 'stop']


@pytest.mark.parametrize(('vm', 'target'), [(vm_name(0), 'ubuntu'), (vm_name(1), 'fedora')])
@pytest.mark.parametrize('selector', ['check_fixture_e2e_installed', 'check_fixture_e2e_product_free'])
def test_e2e_qualification_freezes_input_and_source_proof(monkeypatch, frozen_fixture_selection, vm, target, selector):
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    selected = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('runtime-ubuntu-', 'runtime-' + target + '-'))
    record = selected.record()
    source = source_proof_selection(selected)
    def execute(command, **options):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py',
            '--target', target, '--qualify-source-edit')
        options['output'](('fixture-execution: selection=' + json.dumps(record) + '\n'
            + 'fixture-execution: source-edit=' + json.dumps(source) + '\n').encode())
        return 0
    options = commands.qualification_fixture_options(ROOT, 'integration',
        [selector], control=SimpleNamespace(run=execute), environment={})
    assert options == ['--fixture-selection', json.dumps(record, sort_keys=True),
                       '--fixture-source-selection', json.dumps(source, sort_keys=True)]
    assert commands.qualification_input_options(ROOT, selector) == {
        'vm_source': True, 'fixture_source': True,
        **({'upgrade_source': True} if selector == 'check_fixture_e2e_product_free' else {})}
    dispatch = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['selection']
    command = dispatch(ROOT, ['integration', selector,
                             '--vm', vm, *options])
    assert command[3:] == options


@pytest.mark.parametrize(('category', 'arguments'), [
    ('integration', ['check_e2e_approval_flow']),
    ('integration', ['check_e2e_time_profiles_daily']),
    ('integration', ['check_e2e_native_fixtures']),
    ('e2e', ['--ready']),
])
@pytest.mark.parametrize(('vm', 'target'), [(vm_name(0), 'ubuntu'), (vm_name(1), 'fedora')])
def test_installed_e2e_freezes_before_privileged_dispatch(
        monkeypatch, frozen_fixture_selection, category, arguments, vm, target):
    monkeypatch.setenv('ONPC_TEST_VM', vm)
    record = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('runtime-ubuntu-', 'runtime-' + target + '-')).record()
    def execute(command, **options):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py', '--target', target)
        options['output'](('fixture-execution: selection=' + json.dumps(record) + '\n').encode())
        return 0
    assert commands.qualification_fixture_options(ROOT, category, arguments,
        control=SimpleNamespace(run=execute), environment={}) == [
            '--fixture-selection', json.dumps(record, sort_keys=True)]


@pytest.mark.parametrize('selector', ['check_fixture_e2e_installed', 'check_e2e_approval_flow'])
def test_installed_e2e_refuses_unqualified_target_before_preparing(monkeypatch, selector):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name='unqualified'))
    control = Mock()
    for operation in (
            lambda: commands.plan(ROOT, 'integration', [selector]),
            lambda: commands.qualification_artifact_command(ROOT, 'integration', [selector]),
            lambda: commands.qualification_fixture_options(ROOT, 'integration', [selector], control=control)):
        with pytest.raises(ValueError, match='installed E2E target is unavailable'):
            operation()
    control.run.assert_not_called()


@pytest.mark.parametrize(('vm', 'target'), [(vm_name(0), 'ubuntu'), (vm_name(1), 'fedora')])
def test_e2e_preflight_preserves_frozen_selection_without_opening_bundle(
        monkeypatch, frozen_fixture_selection, vm, target):
    namespace = runpy.run_path(str(ROOT / 'tests/e2e/runner.py'))
    dispatch = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['selection']
    preflight = namespace['preflight']
    monkeypatch.setattr(namespace['password_config'], 'read_password', Mock())
    declarations = {
        'read_json': lambda path: ({}, 'd' * 64),
        'resolve_selection': lambda *args, **kwargs: {'cases': [], 'selector': 'selected'},
    }
    monkeypatch.setattr(namespace['runpy'], 'run_path', lambda path: (
        {'preflight': preflight} if str(path).endswith('/tests/e2e/runner.py') else declarations))
    record = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('runtime-ubuntu-', 'runtime-' + target + '-')).record()
    plan = preflight(['--ready', '--vm', vm,
                      '--fixture-selection', json.dumps(record)], allow_missing_artifacts=True)
    assert plan['fixture_selection'] == record
    assert plan['mode'] == 'execution-preflight'
    command = dispatch(ROOT, ['e2e', '--ready', '--vm', vm,
                       '--fixture-selection', json.dumps(record)], allow_missing_artifacts=True)
    assert command[-2:] == ['--fixture-selection', json.dumps(record, sort_keys=True)]


@pytest.mark.parametrize('suffix', ['', '.py'])
@pytest.mark.parametrize(('vm', 'target'), [(vm_name(0), 'ubuntu'), (vm_name(1), 'fedora')])
def test_fixture_qualification_forwards_exact_frozen_selection(monkeypatch, suffix, vm, target, frozen_fixture_selection):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name=vm))
    selected = replace(frozen_fixture_selection, target=target,
        allocation=frozen_fixture_selection.allocation.replace('ubuntu', target))
    encoded = b'fixture-execution: selection=' + json.dumps(selected.record()).encode() + b'\n'

    def execute(command, **kwargs):
        assert command == commands.python_file(ROOT, 'tools/fixture_execution.py', '--target', target)
        assert kwargs['cwd'] == ROOT and kwargs['env'] == {'PRIVATE': 'environment'}
        assert kwargs['timeout'] == 600.0
        # Split both the prefix and the JSON across callback invocations.
        for chunk in (b'producer progress\n', encoded[:7], encoded[7:42], encoded[42:]):
            kwargs['output'](chunk)
        return 0

    control = SimpleNamespace(run=Mock(side_effect=execute))
    assert commands.qualification_fixture_options(ROOT, 'integration',
        ['check_fixture_provisioning' + suffix], control=control,
        environment={'PRIVATE': 'environment'}) == [
            '--fixture-selection', json.dumps(selected.record(), sort_keys=True)]
    control.run.assert_called_once()


@pytest.mark.parametrize('failure', ['missing', 'duplicate', 'malformed', 'oversized',
    'unterminated', 'foreign-target', 'nonzero'])
@pytest.mark.parametrize(('vm', 'target'), [(vm_name(0), 'ubuntu'), (vm_name(1), 'fedora')])
def test_fixture_qualification_rejects_invalid_child_result(monkeypatch, frozen_fixture_selection, failure, vm, target):
    import vm_selection
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name=vm))
    record = frozen_fixture_selection.record()
    record['target'] = target
    record['allocation'] = record['allocation'].replace('ubuntu', target)
    if failure == 'foreign-target':
        foreign = 'fedora' if target == 'ubuntu' else 'ubuntu'
        record['target'] = foreign
        record['allocation'] = record['allocation'].replace(target, foreign)
    line = b'fixture-execution: selection=' + json.dumps(record).encode() + b'\n'
    output = {'missing': b'progress only\n', 'duplicate': line * 2,
        'malformed': b'fixture-execution: selection={\n',
        'oversized': b'fixture-execution: selection=' + b'x' * 8193 + b'\n',
        'unterminated': line.rstrip(b'\n')}.get(failure, line)

    def execute(command, **kwargs):
        kwargs['output'](output)
        return 9 if failure == 'nonzero' else 0

    control = SimpleNamespace(run=Mock(side_effect=execute))
    with pytest.raises(ValueError):
        commands.qualification_fixture_options(ROOT, 'integration',
            ['check_fixture_provisioning'], control=control, environment={})
    control.run.assert_called_once()


@pytest.mark.parametrize('route', ['category', 'direct'])
@pytest.mark.parametrize('failure', ['none', 'package', 'fixture', 'malformed', 'duplicate'])
def test_fixture_qualification_freezes_after_package_before_privilege(
        monkeypatch, route, failure, frozen_fixture_selection):
    import dev_privileges
    import regression_process
    import vm_selection
    events = []
    monkeypatch.setattr(vm_selection, 'selected', lambda: SimpleNamespace(name=vm_name(0)))
    monkeypatch.setattr(commands, 'plan', lambda *args: (
        [['/usr/bin/pkexec', '/usr/local/libexec/onpc-test-runner',
          'integration', 'check_fixture_provisioning']], False))
    monkeypatch.setattr(commands, 'qualification_artifact_command', lambda *args: ['package-preparation'])
    frozen = frozen_fixture_selection.record()
    monkeypatch.setattr(dev_privileges, 'check', lambda *args: events.append('privilege'))
    executed = []

    def execute(command, **kwargs):
        executed.append(command)
        if 'tools/fixture_execution.py' in ' '.join(command):
            events.append('fixture')
            line = b'fixture-execution: selection=' + json.dumps(frozen).encode() + b'\n'
            if failure == 'malformed':
                line = b'fixture-execution: selection={\n'
            elif failure == 'duplicate':
                line *= 2
            kwargs['output'](line)
            return 9 if failure == 'fixture' else 0
        events.append('package' if command == ['package-preparation'] else 'dispatch')
        status = 7 if command == ['package-preparation'] and failure == 'package' else 0
        return status

    control = SimpleNamespace(run=Mock(side_effect=execute))
    monkeypatch.setattr(regression_process.Control, 'installed', Mock(return_value=nullcontext(control)))
    if route == 'category':
        run = lambda: regression_process.category_run(
            ROOT, 'integration', ['check_fixture_provisioning'], pipe=False)
        if failure in ('fixture', 'malformed', 'duplicate'):
            with pytest.raises(ValueError):
                run()
        else:
            assert run() == (7 if failure == 'package' else 0)
    else:
        monkeypatch.setattr(commands, 'vm_request', lambda argv: (argv, None))
        monkeypatch.setattr(commands, 'host_only_request', lambda argv: True)
        monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
        monkeypatch.setattr(commands.os, 'chdir', Mock())
        import test_storage
        descriptors = (71, 72)
        monkeypatch.setattr(test_storage, 'scratch_descriptors', lambda: descriptors)

        def run(command, **kwargs):
            assert kwargs['pass_fds'] == descriptors
            return SimpleNamespace(returncode=execute(command, **kwargs))

        monkeypatch.setattr(commands.subprocess, 'run', run)
        assert commands._main(['integration', 'check_fixture_provisioning']) == (
            {'package': 7, 'fixture': 2, 'malformed': 2, 'duplicate': 2}.get(failure, 0))
    if failure == 'package':
        assert events == ['package']
    elif failure in ('fixture', 'malformed', 'duplicate'):
        assert events == ['package', 'fixture']
    else:
        assert events == ['package', 'fixture', 'privilege', 'dispatch']
        assert executed[-1][-2:] == ['--fixture-selection', json.dumps(frozen, sort_keys=True)]


@pytest.mark.parametrize('options', [
    ['build', '--kind', 'native-runtime'],
    ['build', '--kind', 'native-runtime', '--target', 'other'],
    ['build', '--kind', 'native-runtime', '--target', 'ubuntu', '--output', '/elsewhere'],
    ['verify', '--kind', 'native-runtime', '--target', 'ubuntu'],
    ['build', '--target', 'ubuntu', '--kind', 'native-runtime'],
])
def test_native_fixture_options_refuse_before_allocating(options):
    with pytest.raises(ValueError):
        commands.plan(ROOT, 'fixtures', options)


def test_native_fixture_category_registers_build_output_before_execution(monkeypatch, tmp_path):
    import regression_process
    output = str(tmp_path)
    allocation = Mock(return_value=output)
    monkeypatch.setattr(regression_process.Control, 'run', Mock(return_value=0))
    import test_retention
    monkeypatch.setattr(test_retention, 'allocate', allocation)
    assert regression_process.category_run(ROOT, 'fixtures',
        ['build', '--kind', 'native-runtime', '--target', 'ubuntu'], pipe=False) == 0
    assert allocation.call_count == 1
    assert regression_process.Control.run.call_args.args[0] == commands.python_file(
        ROOT, 'tools/fixture_bundle.py', '--target', 'ubuntu', '--output', output)


@pytest.mark.parametrize('status,package_format', [(3, 'deb'), (5, 'rpm'), (6, None), (0, None), (130, None)])
@pytest.mark.parametrize('candidate_format', [None, 'deb', 'rpm'])
def test_vm_artifacts_use_verified_platform_and_preserve_probe_failures(
        tmp_path, monkeypatch, capsys, status, package_format, candidate_format):
    import vm_artifacts
    import build_test_artifacts
    configured = vm_artifacts.selected()
    monkeypatch.setattr(vm_artifacts, 'selected', lambda: replace(configured, package_format=package_format or 'deb'))
    output = tmp_path / 'output'
    candidate = tmp_path / 'candidate' if candidate_format else None
    verify = Mock(return_value={'artifacts': {'package': {'path': 'app.' + str(candidate_format)}}})
    monkeypatch.setattr(build_test_artifacts, 'verify', verify)
    authorize = Mock()
    monkeypatch.setattr(vm_artifacts, 'check', authorize)
    allocate = Mock(return_value=str(output))
    monkeypatch.setattr(vm_artifacts.test_retention, 'allocate', allocate)
    control = Mock()
    control.run.side_effect = [status, 0]
    result = vm_artifacts.prepare(ROOT, control, {}, candidate=candidate)
    authorize.assert_called_once_with('/usr/local/libexec/onpc-test-runner')
    assert control.run.call_args_list[0].args[0] == [
        '/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
        '/usr/local/libexec/onpc-test-runner', 'appsnapshot', '--probe',
        '--overwrite', 'true', *VM_ARGS]
    if package_format is None:
        assert result == (status or 2)
        assert control.run.call_count == 1
        allocate.assert_not_called()
        verify.assert_not_called()
    elif candidate_format == package_format:
        assert result == 0 and control.run.call_count == 1
        allocate.assert_not_called()
        verify.assert_called_once_with(candidate)
        assert capsys.readouterr().out.strip() == 'run-tests: output=' + str(candidate)
    else:
        assert result == 0
        assert control.run.call_args.args[0] == [
            '/usr/bin/python3', '-B', str(ROOT / 'tools/build_test_artifacts.py'),
            *(['--reuse'] if package_format == 'deb' else []),
            '--package-format', package_format, '--output', str(output)]
        allocate.assert_called_once()


@pytest.mark.parametrize('options', [
    ['prepare', '--upgrade-inputs'],
    ['prepare', '--for-vm', '--upgrade-inputs', '--upgrade-inputs'],
    ['prepare', '--for-vm', '--upgrade-inputs', '--unknown'],
])
def test_upgrade_preparation_rejects_unvalidated_option_shapes(options):
    with pytest.raises(ValueError, match='invalid artifact operation'):
        commands.plan(ROOT, 'artifacts', options)


@pytest.mark.parametrize('status,package_format', [(3, 'deb'), (5, 'rpm')])
@pytest.mark.parametrize('candidate', [False, True])
def test_vm_upgrade_preparation_uses_verified_format_and_owned_allocation(
        tmp_path, monkeypatch, status, package_format, candidate):
    import vm_artifacts
    import build_test_artifacts
    configured = replace(vm_artifacts.selected(), package_format=package_format)
    monkeypatch.setattr(vm_artifacts, 'selected', lambda: configured)
    monkeypatch.setattr(vm_artifacts, 'check', Mock())
    output = tmp_path / 'output'
    allocate = Mock(return_value=str(output))
    monkeypatch.setattr(vm_artifacts.test_retention, 'allocate', allocate)
    verify = Mock(return_value={'packages': {'current': {
        'architecture': {'deb': 'amd64', 'rpm': 'x86_64'}[package_format]}}})
    monkeypatch.setattr(build_test_artifacts, 'verify_upgrade', verify)
    control = Mock()
    control.run.side_effect = [status, 0]
    assert vm_artifacts.prepare(ROOT, control, {}, upgrade_inputs=True,
                                candidate=output if candidate else None) == 0
    if candidate:
        verify.assert_called_once_with(output)
        allocate.assert_not_called()
        assert control.run.call_count == 1
    else:
        allocate.assert_called_once_with(vm_artifacts.tempfile.mkdtemp, prefix='onpc-test-artifacts-')
        verify.assert_not_called()
        assert control.run.call_args.args[0] == [
            '/usr/bin/python3', '-B', str(ROOT / 'tools/build_test_artifacts.py'),
            '--upgrade-inputs', '--package-format', package_format, '--output', str(output)]


@pytest.mark.parametrize('declared,baseline', [('deb', 5), ('rpm', 3), (None, 5)])
def test_vm_preparation_never_defaults_or_builds_for_mismatched_configuration(
        tmp_path, monkeypatch, declared, baseline):
    import vm_artifacts
    configured = replace(vm_artifacts.selected(), package_format=declared)
    monkeypatch.setattr(vm_artifacts, 'selected', lambda: configured)
    authorize = Mock()
    monkeypatch.setattr(vm_artifacts, 'check', authorize)
    allocate = Mock(side_effect=AssertionError('invalid declaration allocated output'))
    monkeypatch.setattr(vm_artifacts.test_retention, 'allocate', allocate)
    control = Mock()
    control.run.return_value = baseline
    if declared is None:
        with pytest.raises(ValueError, match='package_format'):
            vm_artifacts.prepare(ROOT, control, {})
        authorize.assert_not_called()
        control.run.assert_not_called()
    else:
        assert vm_artifacts.prepare(ROOT, control, {}) == 2
        assert control.run.call_count == 1
    allocate.assert_not_called()


@pytest.mark.parametrize('status', [0, 7, 130])
@pytest.mark.parametrize('equal_form', [False, True])
def test_focused_system_prepares_private_inputs_preserving_selectors_and_guards(
        monkeypatch, status, equal_form, frozen_fixture_selection):
    import dev_privileges
    import regression_process
    import test_retention

    selectors = (['--area=authorization', '--test=case[param]'] if equal_form else
                 ['--area', 'authorization', '--test', 'case[param]'])
    previous = '/tmp/onpc-previous'
    args = [*selectors, '--previous-artifacts', previous,
            '--completed-cases=["prior-case"]', '--qualification-failure', '--skip-backing-verification']
    # The real checkout preflight validates all options before allocating inputs.
    planned, _ = commands.plan(ROOT, 'system', args)
    assert not commands.has_artifacts(planned[0])
    output = '/tmp/onpc-focused-system'
    allocate = Mock(return_value=str(output))
    monkeypatch.setattr(test_retention, 'allocate', allocate)
    monkeypatch.setattr(test_retention, 'token', lambda: 'a' * 32)
    authorize = Mock()
    monkeypatch.setattr(dev_privileges, 'check', authorize)
    frozen = ['--fixture-selection', json.dumps(frozen_fixture_selection.record(), sort_keys=True)]
    freeze = Mock(return_value=frozen)
    monkeypatch.setattr(commands, 'qualification_fixture_options', freeze)
    execute = Mock(side_effect=[status, 0])
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    assert regression_process.category_run(ROOT, 'system', args, pipe=False) == status
    allocate.assert_called_once()
    assert 'dir' not in allocate.call_args.kwargs
    assert execute.call_args_list[0].args[0] == commands.python_file(
        ROOT, 'tools/vm_artifacts.py', '--output', str(output), *VM_ARGS)
    if status:
        assert execute.call_count == 1
        authorize.assert_not_called()
        freeze.assert_not_called()
    else:
        authorize.assert_called_once_with('/usr/local/libexec/onpc-test-runner')
        assert execute.call_args.args[0] == [
            '/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
            '/usr/local/libexec/onpc-test-runner', '--retention-run=' + 'a' * 32,
            '--unattended', 'system', *args, '--artifacts=' + str(output), *VM_ARGS, *frozen]
        assert freeze.call_args.args == (ROOT, 'system', args)
        assert execute.call_args.kwargs['cooperative'] is True


@pytest.mark.parametrize('equal_form', [False, True])
def test_focused_system_preserves_explicit_artifact_input_without_building(monkeypatch, equal_form):
    import dev_privileges
    import regression_process
    import test_retention

    artifact = '/tmp/onpc-explicit'
    args = [*(('--artifacts=' + artifact,) if equal_form else ('--artifacts', artifact)),
            '--area=authorization', '--test=case[param]']
    monkeypatch.setattr(test_retention, 'allocate', Mock(side_effect=AssertionError('replaced explicit input')))
    monkeypatch.setattr(dev_privileges, 'check', Mock())
    monkeypatch.setattr(commands, 'qualification_fixture_options', Mock(return_value=[]))
    execute = Mock(return_value=0)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    assert regression_process.category_run(ROOT, 'system', args, pipe=False) == 0
    execute.assert_called_once()
    assert execute.call_args.args[0][0] == '/usr/bin/pkexec'
    assert args == execute.call_args.args[0][-len(args) - len(VM_ARGS):-len(VM_ARGS)]


@pytest.mark.parametrize('target', [vm_name(0), vm_name(1)])
@pytest.mark.parametrize('status', [0, 7, 130])
def test_shared_upgrade_preparation_binds_each_vm_before_existing_system_dispatch(
        monkeypatch, target, status):
    import dev_privileges
    import regression_process
    import test_retention

    monkeypatch.setenv('ONPC_TEST_VM', target)
    output = str(ROOT / 'output/test-runs/host/allocations/onpc-upgrade-input')
    monkeypatch.setattr(test_retention, 'allocate', Mock(return_value=output))
    monkeypatch.setattr(test_retention, 'token', lambda: None)
    authorize = Mock()
    monkeypatch.setattr(dev_privileges, 'check', authorize)
    monkeypatch.setattr(commands, 'qualification_fixture_options', Mock(return_value=[]))
    execute = Mock(side_effect=[status, 0])
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    args = ['--id', '287', '--upgrade-inputs']
    assert regression_process.category_run(ROOT, 'system', args, pipe=False) == status
    assert execute.call_args_list[0].args[0] == commands.python_file(
        ROOT, 'tools/vm_artifacts.py', '--upgrade-inputs', '--output', output,
        '--vm', target)
    if status:
        assert execute.call_count == 1
        authorize.assert_not_called()
    else:
        assert execute.call_args.args[0] == [
            '/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
            '/usr/local/libexec/onpc-test-runner', '--unattended', 'system',
            '--id', '287', '--artifacts=' + output + '/current',
            '--previous-artifacts=' + output + '/previous', '--vm', target]


@pytest.mark.parametrize('category,args', [
    ('system', ['--upgrade-inputs', '--upgrade-inputs']),
    ('system', ['--upgrade-inputs', '--artifacts=/tmp/onpc-explicit']),
    ('system', ['--upgrade-inputs', '--previous-artifacts', '/tmp/onpc-explicit']),
    ('e2e', ['--upgrade-inputs']),
    ('integration', ['check_e2e_package_upgrade', '--upgrade-inputs']),
])
def test_shared_upgrade_preparation_refuses_conflicts_before_allocation(monkeypatch, category, args):
    import regression_process
    import test_retention

    allocate = Mock(side_effect=AssertionError('invalid request allocated inputs'))
    monkeypatch.setattr(test_retention, 'allocate', allocate)
    with pytest.raises(ValueError, match='upgrade inputs require'):
        regression_process.category_run(ROOT, category, args, pipe=False)
    allocate.assert_not_called()


@pytest.mark.parametrize('target', [vm_name(0), vm_name(1)])
def test_upgrade_checkpoint_retains_the_complete_indivisible_history(monkeypatch, target):
    import regression
    import system_runner
    from tests.support.vm_runner import INVENTORIES

    monkeypatch.setenv('ONPC_TEST_VM', target)
    inventories = {**INVENTORIES, 'package': (
        *INVENTORIES['package'], 'test_previous_package_policy_preservation')}
    monkeypatch.setattr(system_runner, 'collect_area_cases', lambda area: inventories[area])
    options = ['--id', '287', '--upgrade-inputs']
    checkpoint = SimpleNamespace(entry=lambda _: {'args': options}, passed=lambda _: set(),
                                 retry_case=None)
    selected, passed = regression.Run.system_resume_cases(
        SimpleNamespace(root=ROOT, checkpoint=checkpoint), options)
    assert selected == {phase + '::test_previous_package_policy_preservation'
                        for phase in ('previous-policy', 'installed', 'rebooted')}
    assert not passed


def test_dispatcher_still_requires_artifacts_for_actual_system_execution():
    dispatcher = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))
    args = ['system', '--area=authorization', '--test=case[param]', *VM_ARGS]
    with pytest.raises(ValueError, match='test-runner:invalid-arguments'):
        dispatcher['selection'](ROOT, args)
    prepared = dispatcher['selection'](ROOT, args, allow_missing_artifacts=True)
    assert prepared[-2:] == ['--area=authorization', '--test=case[param]']


@pytest.mark.parametrize('args', [
    ['--area='], ['--test=bad\nselector'], ['--unknown'], ['--artifacts=relative'],
    ['--previous-artifacts=relative'], ['--completed-cases=invalid'],
])
def test_invalid_focused_system_selection_refuses_before_package_preparation(monkeypatch, args):
    import regression_process
    execute = Mock(side_effect=AssertionError('invalid selection started preparation'))
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    with pytest.raises(ValueError):
        regression_process.category_run(ROOT, 'system', args, pipe=False)
    execute.assert_not_called()


@pytest.mark.parametrize('args', [
    ['--id='], ['--id=0'], ['--id=01'], ['--id=1,1'], ['--id=999999'],
    ['--id=1,'], ['--id=1, 6'], ['--id=1', '--area=package'],
    ['--id=1', '--test=test_installed_package'], ['--id=1', '--id=6'],
])
def test_invalid_numeric_system_ids_refuse_before_inputs_or_privilege(monkeypatch, args):
    import regression_process
    import dev_privileges
    import test_retention
    execute = Mock(side_effect=AssertionError('invalid IDs launched a child'))
    allocate = Mock(side_effect=AssertionError('invalid IDs allocated artifacts'))
    authorize = Mock(side_effect=AssertionError('invalid IDs checked privilege'))
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    monkeypatch.setattr(test_retention, 'allocate', allocate)
    monkeypatch.setattr(dev_privileges, 'check', authorize)
    with pytest.raises(ValueError):
        regression_process.category_run(ROOT, 'system', args, pipe=False)
    execute.assert_not_called()
    allocate.assert_not_called()
    authorize.assert_not_called()


@pytest.mark.parametrize('args', [['--id', '26,6'], ['--id=26,6']])
def test_numeric_system_dispatch_preserves_explicit_ids_for_runner_resolution(args):
    planned, _ = commands.plan(ROOT, 'system', [*args, '--list'])
    assert '--id=26,6' in planned[0] and '--list' in planned[0]
    assert not any(arg.startswith(('--area', '--test=')) for arg in planned[0])


def test_named_vm_preparation_registers_before_platform_builder(monkeypatch):
    import regression_process
    output = str(ROOT / 'output/test-runs/host/allocations/onpc-native-diagnosis-input')
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    args = ['prepare', '--for-vm', '--output', output]
    planned, safety = commands.plan(ROOT, 'artifacts', args)
    expected = commands.python_file(ROOT, 'tools/vm_artifacts.py', '--output', output, *VM_ARGS)
    assert planned == [expected] and not safety
    allocate = Mock(return_value=output)
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    execute = Mock(return_value=0)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    assert regression_process.category_run(ROOT, 'artifacts', args, pipe=False) == 0
    allocate.assert_called_once_with(output)
    assert execute.call_args.args[0] == expected
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: True)
    with pytest.raises(ValueError, match='artifact output must be a new'):
        commands.plan(ROOT, 'artifacts', args)


@pytest.mark.parametrize('declaration', ['named_input(fixture_source=choose())',
    'named_input(**options)', 'named_input("rpm")',
    'named_input()\nnamed_input(fixture_source=True)'])
def test_ambiguous_input_declaration_refuses_before_allocation(tmp_path, monkeypatch, declaration):
    wrapper = tmp_path / 'check_future.py'
    wrapper.write_text(declaration)
    monkeypatch.setattr(commands.host, 'confined_file', lambda root, path: str(wrapper))
    allocate = Mock()
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    with pytest.raises(ValueError, match='qualification'):
        commands.qualification_artifact_command(ROOT, 'integration', ['check_future'])
    allocate.assert_not_called()


@pytest.mark.parametrize('upgrade', [False, True])
def test_fedora_refuses_wrong_cached_format_before_build(
        tmp_path, monkeypatch, upgrade):
    import vm_artifacts
    import build_test_artifacts
    configured = vm_artifacts.selected()
    monkeypatch.setattr(vm_artifacts, 'selected', lambda: replace(configured, package_format='rpm'))
    candidate = tmp_path / 'existing'
    candidate.mkdir()
    preserved = candidate / 'preserved'
    preserved.write_bytes(b'existing DEB evidence')
    monkeypatch.setattr(vm_artifacts, 'check', Mock())
    verify = Mock(return_value={'artifacts': {'package': {'path': 'package.deb'}}})
    monkeypatch.setattr(build_test_artifacts, 'verify', verify)
    verify_upgrade = Mock(return_value={'packages': {'current': {'architecture': 'amd64'}}})
    monkeypatch.setattr(build_test_artifacts, 'verify_upgrade', verify_upgrade)
    control = Mock()
    control.run.return_value = 5
    assert vm_artifacts.prepare(ROOT, control, {}, candidate=candidate, output=candidate,
                                upgrade_inputs=upgrade) == 2
    assert control.run.call_count == 1
    assert preserved.read_bytes() == b'existing DEB evidence'
    assert verify.call_count == (0 if upgrade else 1)
    assert verify_upgrade.call_count == (1 if upgrade else 0)


@pytest.mark.parametrize('output', [
    '/etc/onpc-input', '/tmp/unrelated', '/tmp/onpc-input/nested',
    '/tmp/../tmp/onpc-input', 'onpc-input', '/tmp//onpc-input',
])
def test_named_artifact_build_refuses_unconfined_outputs(output):
    with pytest.raises(ValueError, match='artifact output'):
        commands.plan(ROOT, 'artifacts', ['build', '--output', output])


def test_named_artifact_build_refuses_existing_and_dangling_paths(monkeypatch):
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: True)
    with pytest.raises(ValueError, match='artifact output'):
        commands.plan(ROOT, 'artifacts', ['build', '--output', '/tmp/onpc-existing'])


def test_named_artifact_allocation_is_exclusive_private_and_retained(tmp_path, monkeypatch):
    import test_retention

    output = tmp_path / 'new-output'
    monkeypatch.setattr(commands, 'artifact_output', lambda _: str(output))
    with test_retention.Store(tmp_path / 'retention').session():
        assert commands.allocate_artifact_output('/tmp/onpc-input') == str(output)
        assert output.stat().st_mode & 0o777 == 0o700
        (output / 'preserve').write_text('existing input')
        with pytest.raises(FileExistsError):
            commands.allocate_artifact_output('/tmp/onpc-input')
        assert (output / 'preserve').read_text() == 'existing input'
    assert str(output) in (tmp_path / 'retention/current.json').read_text()


def test_named_artifact_build_detached_route_registers_before_builder(tmp_path, monkeypatch):
    import regression_process

    output = str(ROOT / 'output/test-runs/host/allocations/onpc-parent-setup-input')
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    allocate = Mock(return_value=output)
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    execute = Mock(return_value=0)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    assert regression_process.category_run(
        ROOT, 'artifacts', ['build', '--output', output], pipe=False) == 0
    allocate.assert_called_once_with(output)
    assert execute.call_args.args[0] == commands.python_file(
        ROOT, 'tools/build_test_artifacts.py', '--package-format', 'deb', '--output', output)




@pytest.mark.parametrize('selector', ['check_e2e_parent_save',
    'check_e2e_operate_public_connectivity_controls',
    'check_e2e_operate_public_connectivity_controls.py'])
def test_toggle_qualification_reuses_existing_inputs_without_overwriting(
        monkeypatch, synthetic_package_identity, selector):
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: True)
    validate = Mock()
    monkeypatch.setattr(commands, 'artifact_path', validate)
    allocate = Mock(side_effect=AssertionError('existing inputs replaced'))
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    assert commands.qualification_artifact_command(
        ROOT, 'integration', [selector]) == commands.python_file(
            ROOT, 'tools/vm_artifacts.py', '--candidate', str(named_input()),
            '--output', str(named_input()), *VM_ARGS)
    validate.assert_called_once_with(str(named_input()))


def test_retention_permission_failure_identifies_allocation_without_starting_tests(
        tmp_path, monkeypatch, capsys):
    import regression
    import test_retention

    import test_activity
    store = test_retention.Store(test_activity.retention_path(tmp_path))
    with pytest.raises(PermissionError):
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
        assert commands._main(['all', *VM_ARGS]) == 2
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


def test_detached_e2e_failed_build_never_starts_privileged_runner(tmp_path, monkeypatch):
    import regression_process
    monkeypatch.setattr(commands, 'plan', lambda *_: (
        [['/usr/bin/pkexec', '/usr/local/libexec/onpc-test-runner', 'e2e']], False))
    monkeypatch.setattr('tempfile.mkdtemp', lambda **_: str(tmp_path))
    execute = Mock(return_value=130)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    assert regression_process.category_run(ROOT, 'e2e', [], pipe=False) == 130
    execute.assert_called_once()
    assert execute.call_args.args[0][2].endswith('/tools/vm_artifacts.py')


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


def test_ui_globs_environment_timeout_and_exclusions(checkout):
    python = checkout / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to('/usr/bin/python3')
    command = host.pytest_command(checkout, ['--timeout', '360s', 'tests/ui/test_*.py',
                                           '--ignore=tests/ui/test_future.py', '-q'], 'ui')
    assert command[:4] == [str(python), '-B', '-m', 'pytest']
    assert host.ui_timeout(['--timeout', '360s']) == 360
    assert '/usr/bin/timeout' not in command
    assert '-m=not live_e2e' in command
    assert '--ignore=tests/ui/test_future.py' in command
    assert command[-2:] == ['--', 'tests/ui/test_future.py']


@pytest.mark.parametrize('category', ['unit', 'component', 'ui'])
@pytest.mark.parametrize('position', ['before', 'after', 'equals'])
def test_host_timeout_is_owned_by_runner_and_accepts_either_position(checkout, category, position):
    python = checkout / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to('/usr/bin/python3')
    selected = [f'tests/{category}/test_future.py', '-q']
    options = (['--timeout', '180s', *selected] if position == 'before' else
               [*selected, '--timeout', '180s'] if position == 'after' else
               [*selected, '--timeout=180s'])

    command = host.pytest_command(checkout, options, category)

    assert host.pytest_timeout(options, category) == 180
    assert not any(value.startswith('--timeout') for value in command)
    assert command[-2:] == ['--', selected[0]]
    assert ('-m=not live_e2e' in command) is (category == 'ui')


@pytest.mark.parametrize('category', ['unit', 'component', 'ui'])
@pytest.mark.parametrize('options', [
    ['--timeout'], ['--timeout=0'], ['--timeout', 'NaN'],
    ['--timeout', '1s', '--timeout=2s'], ['--timeout', '9' * 305 + 'd'],
])
def test_invalid_host_timeout_refuses_before_execution(checkout, category, options, monkeypatch):
    execute = Mock(side_effect=AssertionError('invalid timeout started a worker'))
    monkeypatch.setattr(host.subprocess, 'run', execute)
    with pytest.raises(ValueError):
        host.run_host(checkout, category, [f'tests/{category}', *options])
    execute.assert_not_called()


@pytest.mark.parametrize('category', ['unit', 'component', 'ui'])
@pytest.mark.parametrize('detached', [False, True])
def test_host_execution_forwards_timeout_to_owned_controller(checkout, category, detached, monkeypatch):
    import regression_process
    python = checkout / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to('/usr/bin/python3')
    execute = Mock(return_value=124)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    monkeypatch.setattr(host, 'test_environment', lambda _: {})
    monkeypatch.chdir(checkout)
    run = regression_process.host_run if detached else host.run_host

    assert run(checkout, category, [f'tests/{category}', '--timeout=3m'],
               **({'pipe': False} if detached else {})) == 124

    assert execute.call_args.kwargs['timeout'] == 180
    assert execute.call_args.kwargs['kill_after'] == host.UI_KILL_AFTER
    assert not any(arg.startswith('--timeout') for arg in execute.call_args.args[0])


@pytest.mark.parametrize(('markers', 'expected'), [
    ([], '-m=not live_e2e'),
    (['-m', 'host_case'], '-m=(host_case) and not live_e2e'),
    (['-m', 'not live_e2e'], '-m=not live_e2e'),
    (['-m', 'live_e2e'], '-m=(live_e2e) and not live_e2e'),
])
def test_ui_launcher_always_excludes_vm_dependent_checks(checkout, markers, expected):
    python = checkout / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True, exist_ok=True)
    python.symlink_to('/usr/bin/python3')

    command = host.pytest_command(checkout, [*markers, 'tests/ui'], 'ui')

    assert expected in command


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
    from pathlib import Path
    assert Path(env['TMPDIR']).is_relative_to(ROOT / 'output/test-runs/host/scratch')
    assert 'TMP' not in env and 'TEMP' not in env
    probe = checkout / 'storage_probe.py'
    probe.write_text('''import os, pathlib, tempfile
with tempfile.TemporaryDirectory(prefix='onpc-storage-probe-') as directory:
    assert pathlib.Path(directory).parent == pathlib.Path(os.environ['TMPDIR'])
    with tempfile.TemporaryFile() as capture:
        assert os.readlink('/proc/self/fd/' + str(capture.fileno())).startswith(os.environ['TMPDIR'] + '/')
        capture.write(b'captured output')
        capture.seek(0)
        assert capture.read() == b'captured output'
''')
    subprocess.run([sys.executable, '-B', str(probe)], env=env, check=True, timeout=10)
    assert host.environment(checkout)['TMPDIR'] == env['TMPDIR']


def test_component_runs_only_selected_tests_without_prerequisite_suite(checkout, monkeypatch):
    prerequisite = Mock(side_effect=ValueError('failed prerequisites'))
    execute = Mock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(host, 'prerequisites', prerequisite)
    monkeypatch.setattr(host.subprocess, 'run', execute)
    monkeypatch.chdir(checkout)
    assert host.run_host(checkout, 'component', []) == 0
    prerequisite.assert_not_called()
    execute.assert_called_once()


@pytest.mark.parametrize('category', ['unit', 'component', 'ui'])
def test_collect_only_never_starts_cleanup(checkout, monkeypatch, category):
    python = checkout / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to('/usr/bin/python3')
    prerequisite = Mock()
    execute = Mock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(host, 'prerequisites', prerequisite)
    monkeypatch.setattr(host.subprocess, 'run', execute)
    if category == 'ui':
        import regression_process
        monkeypatch.setattr(regression_process.Control, 'run',
                            lambda *args, **kwargs: execute().returncode)
    monkeypatch.chdir(checkout)
    host.run_host(checkout, category, ['--collect-only'])
    prerequisite.assert_not_called()
    execute.assert_called_once()


@pytest.mark.parametrize('category', ['unit', 'component', 'ui'])
def test_scheduled_collection_keeps_inventory_protocol_without_execution_ownership(
        checkout, monkeypatch, category):
    from contextlib import contextmanager
    import regression_process
    import test_activity
    @contextmanager
    def installed(controller, *, pipe=True):
        assert pipe is True
        yield controller
    monkeypatch.setattr(regression_process.Control, 'installed', installed)
    python = checkout / '.venv/onpc-ui-tests/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to('/usr/bin/python3')
    monkeypatch.setattr(host, '__file__', str(checkout / 'tools/test_launcher.py'))
    monkeypatch.setattr(host, 'prerequisites', Mock(side_effect=AssertionError('collection cleanup')))
    monkeypatch.setattr(test_activity, 'activity', Mock(side_effect=AssertionError('execution owner')))
    execute = Mock(return_value=0)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    assert host.main(['--unattended', '--collect-only', '--timeout', '180s',
                      f'tests/{category}/test_future.py'], category=category) == 0
    command = execute.call_args.args[0]
    env = execute.call_args.kwargs['env']
    assert env['ONPC_REGRESSION_EVENTS'] == env['ONPC_REGRESSION_INVENTORY'] == '1'
    assert '--collect-only' in command and command[-1] == f'tests/{category}/test_future.py'
    assert execute.call_args.kwargs['timeout'] == 180
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


def test_e2e_listing_is_host_safe_and_pending_execution_refused(monkeypatch):
    plan, safety = commands.plan(ROOT, 'e2e', ['--list'])
    assert 'pkexec' not in plan[0][0]
    assert plan[0][2].endswith('/tests/e2e/runner.py')
    assert '--list' in plan[0]
    assert safety is False
    # Listing loads the shared password module without reading credentials.
    # Supply the unrelated execution prerequisite without using the host .envrc.
    import test_account_password
    password = Mock(return_value='fixture-password')
    monkeypatch.setattr(test_account_password, 'read_password', password)
    with pytest.raises(ValueError, match='selection:pending'):
        commands.plan(ROOT, 'e2e', ['--id=7', '--artifacts=/tmp/onpc-future'])
    password.assert_called_once_with(ROOT)


def test_privileged_parent_symlink_is_rejected(checkout):
    dispatcher = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))
    external = checkout / 'outside'
    external.mkdir()
    (external / 'check_future.py').touch()
    (checkout / 'tests/integration').symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError):
        dispatcher['selection'](checkout, ['integration', 'check_future'])


def test_integration_listing_is_host_safe_and_lists_the_snapshot_binding():
    plan, safety = commands.plan(ROOT, 'integration', ['--list'])
    assert plan == [['/usr/bin/python3', '-B',
                     str(ROOT / 'tests/integration/integration_inventory.py')]]
    assert safety is False
    listing = runpy.run_path(str(ROOT / 'tests/integration/integration_inventory.py'))
    assert 'check_fixture_snapshots' in {item['name'] for item in listing['inventory']()}
    scheduled = listing['runnable']()
    assert scheduled and len(scheduled) == len(set(scheduled))
    assert set(scheduled).isdisjoint(listing['EXCLUDED'])
    assert set(scheduled).isdisjoint({
        'check_test_recovery', 'check_graphical_recovery', 'check_system_recovery',
        'check_tmp_storage', 'check_tmp_storage_cleanup', 'check_storage_migration',
        'check_retained_runs_cleanup'})
    assert {'check_fixture_snapshots', 'check_fixture_live_refresh',
            'check_fixture_system_installed', 'check_graphical_attachment',
            'check_graphical_smoke', 'check_graphical_transport',
            'check_graphical_serial', 'check_e2e_watch',
            'check_e2e_upgrade_assets',
            'check_e2e_give_repeated_public_operations_distinct_stages'
            }.isdisjoint(scheduled)
    assert {'check_e2e_baseline_journey', 'check_fixture_e2e_installed',
            'check_graphical_credentials', 'check_graphical_worker'} <= set(scheduled)
    ubuntu = set(listing['runnable'](host_os='ubuntu'))
    fedora = set(listing['runnable'](host_os='fedora'))
    assert ubuntu - fedora == {'check_package_notice'}
    assert fedora <= ubuntu
    assert all(item['excluded_reason'] for item in listing['inventory'](host_os='fedora')
               if item['name'] in ubuntu - fedora)
    assert commands.execution_selections(ROOT, [('integration', [])]) == [
        ('integration', [name]) for name in scheduled]
    assert commands.execution_selections(ROOT, [('system', [])]) == [
        ('system', []), ('system', ['--id', '287', '--upgrade-inputs']),
        ('system', ['--id', '288', '--upgrade-inputs'])]
    dispatcher = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))
    with pytest.raises(ValueError, match='list-does-not-select-test'):
        dispatcher['selection'](ROOT, ['integration', '--list', 'check_fixture_snapshots'])


@pytest.mark.parametrize('category', ['all', 'all-verify'])
def test_aggregate_dispatch_selects_policy_and_rejects_narrowing(monkeypatch, category):
    import regression
    execute = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', execute)
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    assert commands._main([category, *VM_ARGS]) == 7
    execute.assert_called_once_with(ROOT)
    execute.reset_mock()
    assert commands._main([category, '--skip-backing-verification', *VM_ARGS]) == 2
    execute.assert_not_called()


@pytest.mark.parametrize('category', ['all', 'all-verify', 'host', 'host-builds', 'vm'])
def test_continue_on_errors_is_a_valueless_aggregate_flag(monkeypatch, category):
    import regression
    execute = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', execute)
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    assert commands._main([category, '--continue-on-errors', *VM_ARGS]) == 7
    assert execute.call_args.kwargs['continue_on_errors'] is True
    if category == 'host-builds':
        assert execute.call_args.kwargs['serial_builds'] is False
        for args in (['--serial-builds', '--continue-on-errors'],
                     ['--continue-on-errors', '--serial-builds']):
            assert commands._main([category, *args, *VM_ARGS]) == 7
            assert execute.call_args.kwargs['serial_builds'] is True
    execute.reset_mock()
    for args in (['--continue-on-errors=true'], ['--continue-on-errors', 'true'],
                 ['--continue-on-errors', '--continue-on-errors']):
        assert commands._main([category, *args, *VM_ARGS]) == 2
    execute.assert_not_called()


def test_host_aggregate_dispatch_and_invalid_arguments(monkeypatch):
    import regression
    execute = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', execute)
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    assert commands._main(['host']) == 7
    execute.assert_called_once_with(ROOT, phases=('host',))
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
    ['vm'], ['host', 'vm'], ['vm', 'host'], ['vm', 'system'], ['e2e', 'vm'],
])
@pytest.mark.parametrize('detached', [False, True])
def test_complete_categories_share_one_ordered_aggregate(monkeypatch, argv, detached):
    import regression
    execute = Mock(return_value=7)
    monkeypatch.setattr(regression, 'main', execute)
    monkeypatch.setattr(commands.os, 'geteuid', lambda: 1000)
    phases = tuple(kind for kind in ('host', 'system', 'integration', 'e2e')
                   if kind in argv or (kind != 'host' and 'vm' in argv))
    for flag in ([], ['--continue-on-errors']):
        commands.validate(ROOT, [*argv, *flag, *VM_ARGS])
        assert commands.selections(ROOT, [*argv, *flag]) == [(kind, []) for kind in phases]
        assert commands._main([*argv, *flag, *VM_ARGS], detached=detached) == 7
        options = {'continue_on_errors': True} if flag else {}
        execute.assert_called_with(ROOT, phases=phases,
                                   **options)


@pytest.mark.parametrize('argv', [
    ['host', 'host'], ['system', 'e2e', 'system'], ['all', 'host'],
    ['host', 'system', '--bad'], ['host', 'system', '--list'],
    ['host', 'system', '--continue-on-errors', '--continue-on-errors'],
    ['vm', 'vm'], ['vm', '--bad'], ['host', 'vm', '--serial-builds'],
])
def test_invalid_complete_combinations_are_refused_before_work(argv):
    with pytest.raises(ValueError):
        commands.validate(ROOT, argv)
