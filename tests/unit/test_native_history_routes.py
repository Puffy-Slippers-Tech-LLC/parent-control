"""Host-only composition of per-target native transaction history inputs."""

from dataclasses import replace
from pathlib import Path
import stat
from unittest.mock import Mock

import pytest

import regression_process
import test_commands as commands
import test_retention
import vm_artifacts
from tests.support.paths import ROOT
from tests.support.vm_registry import vm_name


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
def test_native_history_applicability_refuses_before_build(monkeypatch, ids):
    execute = Mock(side_effect=AssertionError('invalid selector started a build'))
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    with pytest.raises(ValueError, match='selection:'):
        regression_process.category_run(
            ROOT, 'system', ['--id', ids, '--native-inputs'], pipe=False)
    execute.assert_not_called()


def test_pending_native_history_refuses_before_product_build(monkeypatch):
    execute = Mock(side_effect=AssertionError('missing input started a product build'))
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    with pytest.raises(ValueError, match='selection:numeric-id-not-runnable'):
        regression_process.category_run(ROOT, 'system', ['--id', '289'], pipe=False)
    execute.assert_not_called()


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


def test_explicit_native_inputs_require_one_target(monkeypatch):
    from vm_selection import BATCH, VARIABLE, vm_config

    # Use branch-independent fixture targets so checkout reservations cannot
    # reject this host-only request before the native-input queue guard runs.
    concurrency, configured = vm_config.configuration()
    configured = {name: replace(vm, owning_branch='') for name, vm in configured.items()}
    monkeypatch.setattr(vm_config, 'configuration', lambda path=None: (concurrency, configured))
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
