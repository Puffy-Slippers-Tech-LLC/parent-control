"""Real pytest qualification hooks and host-only provenance/failure regressions."""

import json
import shutil
from unittest.mock import Mock
import xml.etree.ElementTree as ET

import pytest
from test_system_runner import runner, INVENTORIES, RUN, write_junit_results
from test_authentication_evidence import collect_local


def selection(enabled=True):
    return runner.resolve_selection('authorization', runner.QUALIFICATION_CASE,
                                    qualification_failure=enabled, inventories={
        **INVENTORIES, 'authorization': (runner.QUALIFICATION_CASE,)})


@pytest.mark.parametrize(('area', 'case'), [
    (None, None), ('authorization', None), ('package', 'test_installed_package'),
    ('authorization', 'test_method_role_matrix[ListManagedUsers-child1]'),
])
def test_qualification_refuses_other_scopes_before_collection(monkeypatch, area, case):
    collect = Mock(side_effect=AssertionError('collection must not run'))
    monkeypatch.setattr(runner, 'collect_area_cases', collect)
    with pytest.raises(runner.Error, match='qualification:requires-allowlisted-case'):
        runner.resolve_selection(area, case, qualification_failure=True)
    collect.assert_not_called()


def test_qualification_is_frozen_labeled_and_only_loaded_for_authorization(tmp_path):
    normal, qualified = selection(False), selection()
    normal_digest = runner.stage_selected_inputs(normal, tmp_path / 'normal')
    fault_digest = runner.stage_selected_inputs(qualified, tmp_path / 'fault')
    assert normal.executions == qualified.executions
    assert len(qualified.executions) == 5
    assert normal_digest != fault_digest
    identity = json.loads((tmp_path / 'fault/selected-inputs.json').read_text())
    assert identity['selection']['qualification_failure'] is True
    plugin = tmp_path / 'fault/system_qualification.py'
    assert identity['files']['system_qualification.py']['sha256'] == runner.baseline.digest(plugin)
    assert not (tmp_path / 'normal/system_qualification.py').exists()
    for phase in qualified.phases:
        command = runner.pytest_command(RUN, phase, qualified)
        assert ('--onpc-qualification-failure' in command) == (phase == 'authorization')
        assert '--onpc-qualification-failure' not in runner.pytest_command(RUN, phase, normal)
    assert runner.selection_evidence(tmp_path, qualified)['purpose'] == 'harness-qualification'


@pytest.mark.parametrize(('enabled', 'behavior', 'cases', 'expected'), [
    (False, 'pass', ('parent1',), 0),
    (True, 'pass', ('parent1',), 1),
    (True, 'fail', ('parent1',), 1),
    (True, 'skip', ('parent1',), 0),
    (True, 'setup-fail', ('parent1',), 1),
    (True, 'pass', ('child1',), 4),
    (True, 'pass', ('parent1', 'child1'), 4),
    (True, 'pass', (), 4),
])
def test_real_hook_preserves_assertions_and_refuses_scope(
        monkeypatch, tmp_path, enabled, behavior, cases, expected):
    payload = tmp_path / 'payload'
    results = payload / 'results'
    results.mkdir(parents=True)
    shutil.copyfile(runner.ROOT / 'tests/integration/system_qualification.py',
                    payload / 'system_qualification.py')
    sample = payload / 'test_authorization.py'
    # Synthetic host-safe case: no installed fixtures, OS calls or VM guards bypassed.
    sample.write_text(
        'from pathlib import Path\nimport pytest\n'
        '@pytest.fixture(autouse=True)\ndef setup():\n'
        f'    if {behavior!r} == "setup-fail": pytest.fail("original-setup-failure")\n'
        f'@pytest.mark.parametrize("role", {cases!r}, '
        f'ids={["ListManagedUsers-" + role for role in cases]!r})\n'
        'def test_method_role_matrix(role):\n'
        f'    if {behavior!r} == "fail": pytest.fail("original-assertion-failure")\n'
        f'    if {behavior!r} == "skip": pytest.skip("original-skip")\n'
        '    Path(__file__).with_suffix(".called").write_text("real assertion completed")\n'
    )
    commands = runner.Commands()
    commands.run([
        'env', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1', 'PYTHONDONTWRITEBYTECODE=1',
        f'PYTHONPATH={payload}', '/usr/bin/python3', '-B', '-m', 'pytest',
        '-c', str(runner.ROOT / 'tests/system/pytest.ini'), '--noconftest',
        '--rootdir', str(payload), '-p', 'system_qualification',
        *(['--onpc-qualification-failure'] if enabled else []),
        '--junitxml', str(results / 'authorization.xml'), '-q', str(sample),
    ], check=False, timeout=60)
    assert commands.last_returncode == expected
    if expected == 4:
        assert not sample.with_suffix('.called').exists()
        return
    collect_local(monkeypatch, tmp_path, payload)
    tree = ET.parse(results / 'authorization.xml')
    failures = list(tree.iter('failure'))
    if enabled and behavior == 'pass':
        assert sample.with_suffix('.called').read_text() == 'real assertion completed'
        assert len(failures) == 1
        assert failures[0].get('message') == 'Failed: ' + runner.QUALIFICATION_FAILURE
        write_junit_results(tmp_path, selection())
        shutil.copyfile(results / 'authorization.xml', tmp_path / 'guest-results/authorization.xml')
        assert runner.is_qualification_failure(tmp_path, selection())
    else:
        assert runner.QUALIFICATION_FAILURE not in ET.tostring(tree.getroot()).decode()
        if behavior == 'fail':
            assert failures[0].get('message') == 'Failed: original-assertion-failure'


@pytest.mark.parametrize('fault', ['fixed', 'real', 'missing', 'duplicate', 'collection',
                                 'error', 'skipped'])
def test_guarded_failure_classification_preserves_scope_and_original_error(tmp_path, fault):
    selected = selection()
    write_junit_results(tmp_path, selected, fault if fault in {'missing', 'duplicate'} else None)
    path = tmp_path / 'guest-results/authorization.xml'
    tree = ET.parse(path)
    if fault not in {'missing', 'duplicate'}:
        tree.getroot().set('failures', '1')
        ET.SubElement(tree.find('testcase'), 'failure', message=(
            'Failed: ' + runner.QUALIFICATION_FAILURE if fault != 'real'
            else 'original-assertion-failure'))
        if fault in {'error', 'skipped'}:
            # Empty leaf elements must be detected even with inconsistent counters.
            ET.SubElement(tree.find('testcase'), fault)
        tree.write(path)
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    original = runner.CommandError('command:failed:ssh')
    vm.commands.last_returncode = 1
    vm.call.side_effect = [b'', b'', b'', b'', original,
                           runner.CommandError('collection:failed') if fault == 'collection' else b'']
    ledger = runner.RunLedger()
    with pytest.raises(runner.CommandError) as caught:
        runner.installed_run(vm, lease, tmp_path, selected, ledger)
    assert caught.value is original
    category = runner.record_caught_failure(ledger, original)
    assert category == (runner.QUALIFICATION_FAILURE if fault == 'fixed'
                        else 'pytest:failed:authorization')
    assert ledger.outcomes['collection']['outcome'] == (
        'failed' if fault == 'collection' else 'passed')
    if fault == 'fixed':
        assert ledger.outcomes['infrastructure']['category'] == runner.QUALIFICATION_FAILURE
        assert ledger.outcomes['product']['outcome'] == 'not-run'


def test_missing_injected_fault_cannot_become_a_passing_run(tmp_path):
    selected = selection()
    write_junit_results(tmp_path, selected)
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    ledger = runner.RunLedger()
    with pytest.raises(runner.Error, match='harness:qualification-fault-missing'):
        runner.installed_run(vm, lease, tmp_path, selected, ledger)
    assert ledger.outcomes['infrastructure']['category'] == 'harness:qualification-fault-missing'
