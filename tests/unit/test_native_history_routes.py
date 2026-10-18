"""Host-only composition of per-target native transaction history inputs."""

from dataclasses import replace
import json
from pathlib import Path
import stat
from types import SimpleNamespace
from unittest.mock import Mock
import tempfile

import pytest

import regression
import regression_process
import system_runner
import test_commands as commands
import test_retention
import vm_artifacts
from tests.support.paths import ROOT
from tests.support.vm_registry import vm_name
from tests.support.vm_runner import INVENTORIES


@pytest.fixture
def native_inventory(monkeypatch):
    inventories = {**INVENTORIES, 'package': (
        *INVENTORIES['package'], system_runner.NATIVE_UPDATE_CASE)}
    collect = Mock(side_effect=lambda area: inventories[area])
    monkeypatch.setattr(system_runner, 'collect_area_cases', collect)
    return collect


@pytest.mark.parametrize('target', [vm_name(0), vm_name(1)])
@pytest.mark.parametrize('status', [0, 7, 130])
def test_native_preparation_is_owned_by_each_worker_before_dispatch(
        monkeypatch, native_inventory, target, status):
    import dev_privileges

    monkeypatch.setenv('ONPC_TEST_VM', target)
    output = str(ROOT / 'output/test-runs/host/allocations/onpc-native-history')
    allocate = Mock(return_value=output)
    monkeypatch.setattr(test_retention, 'allocate', allocate)
    monkeypatch.setattr(test_retention, 'token', lambda: None)
    authorize = Mock()
    monkeypatch.setattr(dev_privileges, 'check', authorize)
    execute = Mock(side_effect=[status, 0])
    monkeypatch.setattr(regression_process.Control, 'run', execute)

    assert regression_process.category_run(
        ROOT, 'system', ['--id', '289', '--native-inputs'], pipe=False) == status
    allocate.assert_called_once_with(tempfile.mkdtemp,
                                     prefix='onpc-test-artifacts-')
    assert execute.call_args_list[0].args[0] == commands.python_file(
        ROOT, 'tools/vm_artifacts.py', '--system-native-inputs', '--output', output,
        '--vm', target)
    if status:
        assert execute.call_count == 1
        authorize.assert_not_called()
    else:
        assert execute.call_args.args[0] == [
            '/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
            '/usr/local/libexec/onpc-test-runner', '--unattended', 'system',
            '--id', '289', '--artifacts=' + output + '/product',
            '--native-artifacts=' + output + '/native', '--vm', target]


@pytest.mark.parametrize('category,options', [
    ('e2e', ['--native-inputs']),
    ('integration', ['check_anything', '--native-inputs']),
    ('system', ['--native-inputs', '--native-inputs']),
    ('system', ['--native-inputs', '--upgrade-inputs']),
    *[('system', ['--native-inputs', *values]) for values in (
        ['--artifacts', '/tmp/onpc-product'], ['--artifacts=/tmp/onpc-product'],
        ['--previous-artifacts', '/tmp/onpc-old'], ['--previous-artifacts=/tmp/onpc-old'],
        ['--native-artifacts', '/tmp/onpc-native'], ['--native-artifacts=/tmp/onpc-native'])],
])
def test_native_conflicts_refuse_before_any_resource_operation(monkeypatch, category, options):
    allocate = Mock(side_effect=AssertionError('invalid input allocated'))
    execute = Mock(side_effect=AssertionError('invalid input executed'))
    monkeypatch.setattr(test_retention, 'allocate', allocate)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    with pytest.raises(ValueError, match='native inputs require'):
        regression_process.category_run(ROOT, category, options, pipe=False)
    allocate.assert_not_called()
    execute.assert_not_called()


@pytest.mark.parametrize('ids', ['1', '1,289'])
def test_native_history_applicability_refuses_before_build(monkeypatch, native_inventory, ids):
    execute = Mock(side_effect=AssertionError('invalid selector started a build'))
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    with pytest.raises(ValueError, match='selection:'):
        regression_process.category_run(
            ROOT, 'system', ['--id', ids, '--native-inputs'], pipe=False)
    execute.assert_not_called()


def test_native_history_requires_inputs_before_product_build(monkeypatch, native_inventory):
    execute = Mock(side_effect=AssertionError('missing input started a product build'))
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    with pytest.raises(ValueError, match='selection:native-update-requires-native-artifacts'):
        regression_process.category_run(ROOT, 'system', ['--id', '289'], pipe=False)
    execute.assert_not_called()


def test_native_listing_does_not_collect_or_prepare(monkeypatch, native_inventory):
    planned, safety = commands.plan(
        ROOT, 'system', ['--id', '289', '--native-inputs', '--list'])
    assert planned[0][-2:] == ['--id=289', '--list']
    assert '--native-inputs' not in planned[0]
    assert not safety
    native_inventory.assert_not_called()


@pytest.mark.parametrize('options', [
    ['--native-artifacts=relative'],
    ['--native-artifacts=/tmp/onpc-one', '--native-artifacts', '/tmp/onpc-two'],
])
def test_explicit_native_path_guards_run_before_preparation(monkeypatch, options):
    execute = Mock(side_effect=AssertionError('invalid explicit input started preparation'))
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    with pytest.raises(ValueError, match='test-runner:|selection:repeated-native-artifacts'):
        regression_process.category_run(ROOT, 'system', ['--id', '289', *options], pipe=False)
    execute.assert_not_called()


@pytest.mark.parametrize('package_format,probe', [('deb', 3), ('rpm', 5)])
@pytest.mark.parametrize('product_status,native_status', [(0, 0), (9, 0), (0, 7)])
def test_composite_prepares_product_then_native_with_verified_target_format(
        tmp_path, monkeypatch, package_format, probe, product_status, native_status):
    configured = replace(vm_artifacts.selected(), package_format=package_format)
    monkeypatch.setattr(vm_artifacts, 'selected', lambda: configured)
    monkeypatch.setattr(vm_artifacts, 'check', Mock())
    allocate = Mock(side_effect=AssertionError('worker already registered its root'))
    monkeypatch.setattr(test_retention, 'allocate', allocate)
    control = Mock()
    output = tmp_path / 'registered-inputs'
    output.mkdir(mode=0o700)
    identity = output.stat()
    events = []

    def run(command, **kwargs):
        if 'appsnapshot' in command:
            events.append('probe')
            return probe
        from tools import build_test_artifacts, native_transaction_inputs, test_storage

        destination = Path(command[command.index('--output') + 1])
        # Mirror the CLI's strict DEB resolution and the real builders' folder
        # guards, replacing only expensive package/cache/download work.
        assert all(stat.S_IMODE((output / name).stat().st_mode) == 0o700
                   for name in ('product', 'native'))
        if '--native-inputs' in command:
            events.append('native')
            monkeypatch.setattr(test_storage, 'scratch_directory', lambda: tmp_path)
            native_transaction_inputs._safe_tree(destination)
            native_transaction_inputs._begin(destination, package_format)
            return native_status
        events.append('product')
        if '--reuse' in command:
            destination = destination.resolve(strict=True)
        build_test_artifacts._require_empty_output(destination)
        return product_status

    control.run.side_effect = run
    assert vm_artifacts.prepare(ROOT, control, {}, output=output,
                                system_native_inputs=True) == (product_status or native_status)
    builds = [call.args[0] for call in control.run.call_args_list
              if str(ROOT / 'tools/build_test_artifacts.py') in call.args[0]]
    assert builds[0] == commands.python_file(
        ROOT, 'tools/build_test_artifacts.py', *(['--reuse'] if package_format == 'deb' else []),
        '--package-format', package_format, '--output', str(output / 'product'))
    if product_status:
        assert len(builds) == 1
    else:
        assert builds[1] == commands.python_file(
            ROOT, 'tools/build_test_artifacts.py', '--native-inputs',
            '--package-format', package_format, '--output', str(output / 'native'))
    allocate.assert_not_called()
    assert events == (['probe', 'product'] if product_status else
                      ['probe', 'product', 'probe', 'native'])
    assert (output.stat().st_dev, output.stat().st_ino) == (identity.st_dev, identity.st_ino)
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    if product_status:
        assert not list((output / 'native').iterdir())


@pytest.mark.parametrize('entry', ['product', 'native', 'foreign', 'link'])
def test_composite_preserves_existing_entries_before_any_builder(tmp_path, entry):
    output = tmp_path / 'registered-inputs'
    output.mkdir(mode=0o700)
    sentinel = tmp_path / 'sentinel'
    sentinel.write_text('preserve')
    if entry == 'link':
        (output / 'native').symlink_to(sentinel)
    elif entry in ('product', 'native'):
        (output / entry).mkdir(mode=0o700)
    else:
        (output / entry).write_text('foreign payload')
    before = list(output.iterdir())
    control = Mock()
    with pytest.raises(ValueError, match='allocation must be empty'):
        vm_artifacts.prepare(ROOT, control, {}, output=output, system_native_inputs=True)
    control.run.assert_not_called()
    assert list(output.iterdir()) == before
    assert sentinel.read_text() == 'preserve'


@pytest.mark.parametrize('unsafe', ['missing', 'linked', 'public', 'foreign'])
def test_composite_requires_existing_private_caller_root(tmp_path, monkeypatch, unsafe):
    output = tmp_path / 'registered-inputs'
    if unsafe != 'missing':
        output.mkdir(mode=0o700)
    if unsafe == 'linked':
        linked = tmp_path / 'linked-inputs'
        linked.symlink_to(output, target_is_directory=True)
        output = linked
    elif unsafe == 'public':
        output.chmod(0o755)
    elif unsafe == 'foreign':
        # Model foreign ownership without changing host credentials or files.
        monkeypatch.setattr(test_retention.os, 'geteuid', lambda: output.stat().st_uid + 1)
    control = Mock()
    with pytest.raises((ValueError, OSError)):
        vm_artifacts.prepare(ROOT, control, {}, output=output, system_native_inputs=True)
    control.run.assert_not_called()
    if unsafe != 'missing':
        assert not list(output.iterdir())


@pytest.mark.parametrize('conflict', [dict(upgrade_inputs=True), dict(native_inputs=True),
                                      dict(candidate='/tmp/onpc-existing')])
def test_composite_conflicts_refuse_before_probe(monkeypatch, conflict):
    control = Mock()
    select = Mock(side_effect=AssertionError('conflict selected a target'))
    monkeypatch.setattr(vm_artifacts, 'selected', select)
    with pytest.raises(ValueError, match='require new product and native bundles'):
        vm_artifacts.prepare(ROOT, control, {}, system_native_inputs=True, **conflict)
    select.assert_not_called()
    control.run.assert_not_called()


@pytest.mark.parametrize('target', [vm_name(0), vm_name(1)])
def test_native_resume_retains_both_phases(monkeypatch, native_inventory, target):
    monkeypatch.setenv('ONPC_TEST_VM', target)
    options = ['--id', '289', '--native-inputs']
    checkpoint = SimpleNamespace(entry=lambda _: {'args': options}, passed=lambda _: set())
    selected, passed = regression.Run.system_resume_cases(
        SimpleNamespace(root=ROOT, checkpoint=checkpoint), options)
    assert selected == {phase + '::' + system_runner.NATIVE_UPDATE_CASE
                        for phase in system_runner.NATIVE_UPDATE_PHASES}
    assert not passed


def test_explicit_native_inputs_require_one_target(monkeypatch):
    from vm_selection import BATCH, VARIABLE

    monkeypatch.delenv(BATCH, raising=False)
    monkeypatch.setenv(VARIABLE, vm_name(0))
    with pytest.raises(ValueError, match='explicit native artifacts require a single VM'):
        commands.vm_request(['system', '--vm', ','.join([vm_name(0), vm_name(1)]),
                             '--id', '289', '--native-artifacts=/tmp/onpc-native'])
    # Explicit single-target input passes the queue guard; the dispatcher and
    # installed runner retain path and package-format verification ownership.
    args, target = commands.vm_request(['system', '--vm', vm_name(0),
                                       '--id', '289', '--native-artifacts=/tmp/onpc-native'])
    assert target.name == vm_name(0)
    assert '--native-artifacts=/tmp/onpc-native' in args


@pytest.mark.parametrize('kind,reason,category', [
    ('native', 'unreviewed-rpm-trigger-owner', 'native-preflight:unreviewed-rpm-trigger-owner'),
    ('native', 'missing-file:/home/private-person/config', 'native-preflight:missing-file'),
    ('native', '/home/private-person/config', 'native-preflight:invalid-diagnostic'),
    ('value', 'native-preflight:missing-file:/home/private-person/config', 'unexpected-failure'),
])
def test_native_establish_dispatch_preserves_only_safe_preflight_errors(
        tmp_path, monkeypatch, capsys, kind, reason, category):
    import native_transaction as native
    import system_guest as guest
    import system_native_update as update

    guard = Mock(return_value={})
    monkeypatch.setattr(guest, 'guard', guard)
    monkeypatch.setattr(guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(guest, 'before_install', Mock())
    monkeypatch.setattr(update, 'inputs', lambda: ({}, {}, tmp_path))
    monkeypatch.setattr(update, 'private', lambda: tmp_path)

    def refuse(*args):
        if kind == 'native':
            native.require(False, reason)
        raise ValueError(reason)

    monkeypatch.setattr(update, 'preflight', refuse)
    transaction = Mock(side_effect=AssertionError('refused preflight started transaction'))
    monkeypatch.setattr(update, 'transaction', transaction)
    assert guest.main(['native-establish-old']) == 1
    output = capsys.readouterr()
    expected = category + (native.REFRESH if kind == 'native' else '')
    assert output.err == f'onpc-system: outcome=failed category={expected}\n'
    assert not output.out
    assert 'private-person' not in output.err
    guard.assert_called_once_with()
    transaction.assert_not_called()
    # Refusal still precedes every transaction/checkpoint. Its detailed cause
    # now remains in the private evidence route, never the public diagnostic.
    diagnostic = tmp_path / 'native-update-output'
    assert list(tmp_path.iterdir()) == [diagnostic]
    failure = diagnostic / 'old-failure.txt'
    assert list(diagnostic.iterdir()) == [failure]
    assert stat.S_IMODE(failure.stat().st_mode) == 0o600
    assert reason in failure.read_text()


def test_native_preflight_failure_remains_collectable_through_guest_dispatch(
        tmp_path, monkeypatch, capsys):
    import pwd
    import native_transaction as native
    import system_guest as guest
    import system_native_update as update

    marker = dict(run='a' * 32, package_sha256='b' * 64,
                  baseline_sha256='c' * 64, selected_inputs_sha256='d' * 64)
    monkeypatch.setattr(guest, 'PAYLOAD', tmp_path)
    monkeypatch.setattr(guest, 'EXPIRY_DIAGNOSTICS', tmp_path / 'expiry')
    monkeypatch.setattr(guest, 'guard', lambda: marker)
    monkeypatch.setattr(guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(guest, 'before_install', Mock())
    monkeypatch.setattr(update, 'inputs', lambda: ({}, {}, tmp_path))
    private = tmp_path / 'private'
    private.mkdir()
    monkeypatch.setattr(update, 'private', lambda: private)
    stage = private / 'stage-diagnostic'
    stage.mkdir()
    source = stage / 'preflight.txt'
    source.write_text('native database refused for private-person\n')
    hostname = tmp_path / 'hostname'
    hostname.write_text('test-host')
    monkeypatch.setattr(guest, 'Path', lambda value: hostname if str(value) == '/etc/hostname'
                        else tmp_path / 'empty-logs' if str(value) == '/var/log/oh-no-parent-control'
                        else Path(value))
    monkeypatch.setattr(pwd, 'getpwall', lambda: [SimpleNamespace(
        pw_uid=1000, pw_name='private-person', pw_gecos='', pw_dir='/home/private-person')])
    command = Mock()
    command.run.return_value = b''
    monkeypatch.setattr(guest, 'Commands', lambda: command)

    def refuse(*args):
        native.require(False, 'unreviewed-rpm-trigger-owner')

    monkeypatch.setattr(update, 'preflight', refuse)
    assert guest.main(['native-establish-old']) == 1
    assert 'native-preflight:unreviewed-rpm-trigger-owner' in capsys.readouterr().err
    assert guest.main(['collect', 'failed']) == 0
    output = tmp_path / 'results'
    result = json.loads((output / 'result.json').read_text())
    assert result['outcome'] == 'failed'
    assert result['selected_inputs_sha256'] == marker['selected_inputs_sha256']
    assert (output / 'stage-diagnostic-preflight.txt').read_text() == (
        'native database refused for [Test user]\n')
    assert 'private-person' in source.read_text()
    assert not (private / 'native-update-intent.json').exists()
    assert not capsys.readouterr().err
