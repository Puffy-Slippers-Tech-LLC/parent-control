"""Host-only contracts for maintained native dependency input routes."""

from dataclasses import replace
from unittest.mock import Mock

import pytest

from tests.support.modules import load_module
from tests.support.paths import ROOT
import test_commands as commands
import vm_artifacts


MODULE_PATH = ROOT / 'tools/build_test_artifacts.py'
artifacts = load_module('onpc_test_native_artifact_routes', MODULE_PATH)


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_native_builder_dispatches_exact_format_without_product_builds(
        tmp_path, monkeypatch, package_format):
    from tools import native_transaction_inputs

    output = tmp_path / 'native-inputs'
    prepare = Mock()
    monkeypatch.setattr(native_transaction_inputs, 'prepare', prepare)
    product_build = Mock(side_effect=AssertionError('native route built product inputs'))
    monkeypatch.setattr(artifacts, 'build', product_build)
    monkeypatch.setattr(artifacts, 'build_upgrade', product_build)
    monkeypatch.setattr(artifacts.sys, 'argv', [str(MODULE_PATH), '--native-inputs',
        '--package-format', package_format, '--output', str(output)])

    assert artifacts.main() == 0
    prepare.assert_called_once_with(output, package_format=package_format)
    product_build.assert_not_called()
    assert not output.exists()


def test_native_builder_requires_format_before_any_output(tmp_path, monkeypatch, capsys):
    from tools import native_transaction_inputs

    output = tmp_path / 'must-not-exist'
    prepare = Mock()
    monkeypatch.setattr(native_transaction_inputs, 'prepare', prepare)
    monkeypatch.setattr(artifacts.sys, 'argv', [str(MODULE_PATH), '--native-inputs',
                                              '--output', str(output)])
    with pytest.raises(SystemExit) as failure:
        artifacts.main()
    assert failure.value.code == 2
    assert '--package-format deb|rpm is required' in capsys.readouterr().err
    prepare.assert_not_called()
    assert not output.exists()


@pytest.mark.parametrize('conflict', [
    ['--reuse'], ['--upgrade-inputs'], ['--verify'],
    ['--compare', '/tmp/onpc-first', '/tmp/onpc-second'],
    ['--verify-native-inputs'],
])
def test_native_builder_conflicts_refuse_before_writes(tmp_path, monkeypatch, conflict):
    from tools import native_transaction_inputs

    output = tmp_path / 'must-not-exist'
    prepare, verify = Mock(), Mock()
    monkeypatch.setattr(native_transaction_inputs, 'prepare', prepare)
    monkeypatch.setattr(native_transaction_inputs, 'verify', verify)
    monkeypatch.setattr(artifacts.sys, 'argv', [str(MODULE_PATH), '--native-inputs',
        '--package-format', 'deb', '--output', str(output), *conflict])
    assert artifacts.main() == 1
    prepare.assert_not_called()
    verify.assert_not_called()
    assert not output.exists()


@pytest.mark.parametrize('package_format', [None, 'deb', 'rpm'])
def test_native_verification_dispatch_is_read_only(tmp_path, monkeypatch, package_format):
    from tools import native_transaction_inputs

    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    sentinel = candidate / 'retained-input'
    sentinel.write_bytes(b'preserve selected input')
    verify, prepare = Mock(), Mock()
    monkeypatch.setattr(native_transaction_inputs, 'verify', verify)
    monkeypatch.setattr(native_transaction_inputs, 'prepare', prepare)
    monkeypatch.setattr(artifacts.sys, 'argv', [str(MODULE_PATH),
        '--verify-native-inputs', '--output', str(candidate),
        *(['--package-format', package_format] if package_format else [])])
    assert artifacts.main() == 0
    verify.assert_called_once_with(candidate, package_format=package_format)
    prepare.assert_not_called()
    assert sentinel.read_bytes() == b'preserve selected input'


def test_native_routes_are_explicit_maintained_launcher_operations(monkeypatch):
    planned, safety = commands.plan(ROOT, 'artifacts',
                                   ['prepare', '--for-vm', '--native-inputs'])
    assert planned == [commands.python_file(ROOT, 'tools/vm_artifacts.py',
        '--native-inputs', *vm_artifacts.arguments())]
    assert not safety
    path = '/tmp/onpc-native-inputs'
    validate = Mock(return_value=path)
    monkeypatch.setattr(commands, 'artifact_path', validate)
    planned, safety = commands.plan(ROOT, 'artifacts', ['verify-native', path])
    validate.assert_called_once_with(path)
    assert planned == [commands.python_file(ROOT, 'tools/build_test_artifacts.py',
        '--verify-native-inputs', '--output', path)]
    assert not safety


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_native_explicit_format_preparation_needs_no_vm_probe(package_format):
    planned, safety = commands.plan(ROOT, 'artifacts',
        ['prepare', '--native-inputs', '--package-format', package_format])
    assert planned == [commands.python_file(ROOT, 'tools/build_test_artifacts.py',
        '--native-inputs', '--package-format', package_format)]
    assert not safety


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_native_category_registers_allocation_before_builder(
        tmp_path, monkeypatch, package_format):
    import regression_process
    import test_retention
    import tempfile

    output = str(tmp_path / 'registered-native-input')
    allocate = Mock(return_value=output)
    monkeypatch.setattr(test_retention, 'allocate', allocate)
    execute = Mock(return_value=0)
    monkeypatch.setattr(regression_process.Control, 'run', execute)
    assert regression_process.category_run(ROOT, 'artifacts',
        ['prepare', '--native-inputs', '--package-format', package_format], pipe=False) == 0
    allocate.assert_called_once_with(tempfile.mkdtemp,
        prefix='onpc-test-artifacts-', dir='/tmp')
    assert execute.call_args.args[0] == commands.python_file(ROOT,
        'tools/build_test_artifacts.py', '--native-inputs', '--package-format', package_format,
        '--output', output)


@pytest.mark.parametrize('options', [
    ['prepare', '--native-inputs'],
    ['prepare', '--for-vm', '--native-inputs', '--native-inputs'],
    ['prepare', '--for-vm', '--native-inputs', '--upgrade-inputs'],
    ['prepare', '--for-vm', '--native-inputs', '--unknown'],
    ['verify-native'], ['verify-native', '/tmp/onpc-native', '--reuse'],
    ['prepare', '--native-inputs', '--package-format', 'unknown'],
])
def test_native_launcher_rejects_unvalidated_operation_shapes(options):
    with pytest.raises(ValueError, match='invalid artifact operation'):
        commands.plan(ROOT, 'artifacts', options)


@pytest.fixture
def native_vm_route(monkeypatch, tmp_path):
    """Replace every external/resource operation; only private pytest files remain."""
    import native_transaction_inputs

    configured = vm_artifacts.selected()
    authorize = Mock()
    allocate = Mock(return_value=str(tmp_path / 'retained-inputs'))
    verify = Mock()
    monkeypatch.setattr(vm_artifacts, 'check', authorize)
    monkeypatch.setattr(vm_artifacts.test_retention, 'allocate', allocate)
    monkeypatch.setattr(native_transaction_inputs, 'verify', verify)
    return configured, authorize, allocate, verify


@pytest.mark.parametrize('package_format,status', [('deb', 3), ('rpm', 5)])
@pytest.mark.parametrize('explicit_output', [False, True])
def test_native_vm_build_uses_verified_baseline_and_retention_allocation(
        tmp_path, monkeypatch, native_vm_route, package_format, status, explicit_output):
    configured, authorize, allocate, verify = native_vm_route
    monkeypatch.setattr(vm_artifacts, 'selected',
                        lambda: replace(configured, package_format=package_format))
    output = tmp_path / ('explicit-inputs' if explicit_output else 'retained-inputs')
    environment = {'LANG': 'C.UTF-8'}
    control = Mock()
    control.run.side_effect = [status, 7]

    assert vm_artifacts.prepare(ROOT, control, environment, native_inputs=True,
                                output=output if explicit_output else None) == 7
    authorize.assert_called_once_with('/usr/local/libexec/onpc-test-runner')
    assert control.run.call_args_list[0].args[0] == [
        '/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
        '/usr/local/libexec/onpc-test-runner', 'appsnapshot', '--probe',
        '--overwrite', 'true', *vm_artifacts.arguments()]
    assert control.run.call_args_list[1].args[0] == [
        '/usr/bin/python3', '-B', str(MODULE_PATH), '--native-inputs',
        '--package-format', package_format, '--output', str(output)]
    for call in control.run.call_args_list:
        assert call.kwargs == {'cwd': ROOT, 'env': environment}
    if explicit_output:
        allocate.assert_not_called()
    else:
        allocate.assert_called_once_with(vm_artifacts.tempfile.mkdtemp,
                                         prefix='onpc-test-artifacts-')
    verify.assert_not_called()
    assert not output.exists()


@pytest.mark.parametrize('package_format,status', [('deb', 3), ('rpm', 5)])
@pytest.mark.parametrize('rejected', [False, True])
def test_native_vm_candidate_verification_never_allocates_or_repairs(
        tmp_path, monkeypatch, native_vm_route, capsys, package_format, status, rejected):
    configured, _, allocate, verify = native_vm_route
    monkeypatch.setattr(vm_artifacts, 'selected',
                        lambda: replace(configured, package_format=package_format))
    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    sentinel = candidate / 'retained-input'
    sentinel.write_bytes(b'original native input')
    control = Mock()
    control.run.return_value = status
    if rejected:
        verify.side_effect = ValueError('native input digest mismatch')
        with pytest.raises(ValueError, match='native input digest mismatch'):
            vm_artifacts.prepare(ROOT, control, {}, candidate=candidate,
                                 output=candidate, native_inputs=True)
    else:
        assert vm_artifacts.prepare(ROOT, control, {}, candidate=candidate,
                                    output=candidate, native_inputs=True) == 0
        assert capsys.readouterr().out.strip() == 'run-tests: output=' + str(candidate)
    verify.assert_called_once_with(candidate, package_format=package_format)
    allocate.assert_not_called()
    assert control.run.call_count == 1
    assert sentinel.read_bytes() == b'original native input'


@pytest.mark.parametrize('declared,status,expected', [
    ('deb', 5, 2), ('rpm', 3, 2), ('deb', 0, 2),
    ('deb', 6, 6), ('rpm', 130, 130), (None, 3, None),
])
def test_native_vm_refuses_unverified_or_missing_format_without_writes(
        tmp_path, monkeypatch, native_vm_route, declared, status, expected):
    configured, authorize, allocate, verify = native_vm_route
    monkeypatch.setattr(vm_artifacts, 'selected',
                        lambda: replace(configured, package_format=declared))
    control = Mock()
    control.run.return_value = status
    options = {'native_inputs': True, 'candidate': tmp_path / 'candidate'}
    if declared is None:
        with pytest.raises(ValueError, match='package_format'):
            vm_artifacts.prepare(ROOT, control, {}, **options)
        control.run.assert_not_called()
        authorize.assert_not_called()
    else:
        assert vm_artifacts.prepare(ROOT, control, {}, **options) == expected
        assert control.run.call_count == 1
    allocate.assert_not_called()
    verify.assert_not_called()


def test_native_vm_product_upgrade_conflict_refuses_before_external_operations(
        monkeypatch, native_vm_route):
    _, authorize, allocate, verify = native_vm_route
    selected = Mock(side_effect=AssertionError('conflict reached VM selection'))
    monkeypatch.setattr(vm_artifacts, 'selected', selected)
    control = Mock()
    with pytest.raises(ValueError, match='separate operations'):
        vm_artifacts.prepare(ROOT, control, {}, native_inputs=True, upgrade_inputs=True)
    selected.assert_not_called()
    authorize.assert_not_called()
    allocate.assert_not_called()
    verify.assert_not_called()
    control.run.assert_not_called()
