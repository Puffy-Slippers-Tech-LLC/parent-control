"""Shared installed runner dispatch, failure stops and attempt identity."""

import json
from unittest.mock import Mock

import pytest

import system_runner as system
import system_snapshots as snapshots
from tests.support.vm_runner import INVENTORIES, RUN, write_junit_results


@pytest.mark.parametrize('area', [None, 'enforcement'])
def test_attempt_partition_preserves_every_selected_execution(area):
    selection = system.resolve_selection(area, inventories=INVENTORIES)
    planned = snapshots.attempts(selection)
    assert tuple(item for part, _ in planned for item in part.executions) == selection.executions
    for part, installed in planned:
        assert installed == all(item.area != 'package' for item in part.executions)
        if installed:
            assert len(part.phases) == 1
        else:
            assert set(part.phases) <= {'installed', 'rebooted', *system.REMOVAL_PHASES}


@pytest.mark.parametrize('failure', [None, 'prepare', 'test', 'evidence'])
def test_attempts_restore_before_each_area_and_stop_after_failure(tmp_path, monkeypatch, failure):
    import vm_transport
    import guest_inputs
    selection = system.resolve_selection(inventories=INVENTORIES)
    (tmp_path / 'input').mkdir()
    (tmp_path / 'input/frozen').write_bytes(b'input')
    frozen = Mock()
    monkeypatch.setattr(guest_inputs.Bundle, 'from_staged', Mock(return_value=frozen))
    suite = Mock()
    suite.verified = None
    suite.lease = Mock(state={'run': RUN})
    lease = suite.lease
    lease.capture.state = {'guest': {'os_id': 'fedora', 'version': '44'}}
    lease.__enter__ = Mock(return_value=lease)
    lease.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(system, 'bootstrap', Mock(return_value='host-key'))
    monkeypatch.setattr(system, 'address', lambda _: 'guest')
    monkeypatch.setattr(vm_transport, 'Transport', Mock())
    manifest = {'artifacts': {'package': {'sha256': 'package'}}}
    seen = []

    def prepare(case, *args, **kwargs):
        assert case == snapshots.installed_case(True)
        if failure == 'prepare':
            raise system.Error('preparation-refused')

    suite.prepare_case.side_effect = prepare

    def execute(vm, lease, directory, selected, ledger, *, already_installed):
        seen.append(selected.phases)
        assert (directory / 'input/frozen').read_bytes() == b'input'
        write_junit_results(directory, selected)
        (directory / 'guest-results/result.json').write_text(json.dumps({
            'outcome': 'passed', 'package_sha256': 'wrong' if failure == 'evidence' else 'package',
            'selected_inputs_sha256': 'selected'}))
        if failure == 'test' and already_installed:
            raise system.Error('test-refused')

    monkeypatch.setattr(system, 'installed_run', execute)
    ledger = system.RunLedger()
    if failure:
        with pytest.raises(system.Error):
            snapshots.run_attempts(suite, tmp_path, selection, manifest, 'selected', ledger)
        assert len(seen) == (2 if failure == 'test' else 1)
    else:
        snapshots.run_attempts(suite, tmp_path, selection, manifest, 'selected', ledger)
        assert seen == [('installed', 'rebooted', *system.REMOVAL_PHASES),
                        ('authorization',), ('enforcement',), ('session',)]
        assert suite.prepare_case.call_count == 3
        for phase in selection.phases:
            system.reconcile_junit(tmp_path, phase, selection)
    assert lease.prepare.call_count == 1
    assert lease.__enter__.call_count == lease.__exit__.call_count
    lease.source.domain.snapshotLookupByName.assert_not_called()  # Only shared E2E code owns snapshots.
    assert suite._input_bundle is frozen


@pytest.mark.parametrize('fault', [None, 'outcome', 'package_sha256', 'selected_inputs_sha256'])
def test_attempt_result_requires_exact_frozen_package_and_source_inputs(tmp_path, fault):
    (tmp_path / 'guest-results').mkdir()
    result = {'outcome': 'passed', 'package_sha256': 'package', 'selected_inputs_sha256': 'selected'}
    if fault:
        result[fault] = 'foreign'
    (tmp_path / 'guest-results/result.json').write_text(json.dumps(result))
    manifest = {'artifacts': {'package': {'sha256': 'package'}}}
    ledger = system.RunLedger()
    if fault:
        with pytest.raises(system.Error, match='pytest:guest-evidence'):
            snapshots.verify_result(tmp_path, manifest, 'selected', ledger)
        assert ledger.outcomes['collection']['category'] == 'pytest:guest-evidence'
    else:
        snapshots.verify_result(tmp_path, manifest, 'selected', ledger)
