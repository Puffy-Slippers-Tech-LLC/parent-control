"""Host-only composition of per-target native transaction history inputs."""

from dataclasses import replace
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
    control.run.side_effect = [probe, product_status, probe, native_status]
    output = tmp_path / 'registered-inputs'
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
    assert not output.exists()


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
