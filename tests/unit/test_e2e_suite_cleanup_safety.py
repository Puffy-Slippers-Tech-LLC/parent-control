"""Suite transitions with real ownership locks and mocked libvirt only."""

import fcntl
import os
import xml.etree.ElementTree as ET
from contextlib import nullcontext
from unittest.mock import MagicMock, Mock

import pytest

import graphical_lease
import suite_lease
import system_runner as system
from e2e_watch_viewer import progress_text
from tools.e2e_progress import Progress
from tests.support.vm_baseline import rig
from tests.support.vm_runner import lease_rig


@pytest.fixture
def suite(lease_rig):
    original, current = lease_rig
    lease = suite_lease.SuiteLease(original.source, original.commands, Mock(wraps=original.inspect),
        directory=original.directory, anchor=original.capture.anchor,
        graphics_type='vnc', ledger=system.RunLedger())
    lease.source.api.VIR_DOMAIN_SNAPSHOT_REVERT_FORCE = 4
    try:
        yield lease, current
    finally:
        if lease.fd is not None:
            # Host-safe fixture: do not mask a failed test with another audit.
            system.Lease.release(lease)


def run_case(lease):
    lease.ledger = system.RunLedger()
    with lease:
        lease.prepare()
        adapter = graphical_lease.Adapter(lease)
        adapter.request('off', adapter.run)
        adapter.request('on', adapter.run)
        adapter.request('off', adapter.run)
        assert adapter.request('status', adapter.run) == 'off'
    assert lease.attempt_released and lease.fd is not None
    assert lease.state['phase'] == 'complete'


def test_three_cases_restore_once_per_boundary_and_audit_only_at_suite_ends(suite):
    lease, _ = suite
    shutdowns = lease.source.shutdown_calls
    for _ in range(3):
        run_case(lease)
        assert lease.capture.verification_totals['calls'] == 1
        assert lease.inspect.call_count == 1
        # The shared lock remains exclusive even while a case is reported.
        other = os.open(lease.capture.lock_path, os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(other)
    calls = lease.source.domain.revertToSnapshot.call_args_list
    assert [call.args[1] for call in calls] == [0, 4, 4, 4]
    assert lease.source.shutdown_calls == shutdowns + 1  # Initial preflight only.
    lease.source.domain.destroyFlags.assert_not_called()
    lease.audit()
    assert lease.fd is None
    assert lease.capture.verification_totals['calls'] == 2
    assert lease.inspect.call_count == 2
    assert lease.source.domain.revertToSnapshot.call_count == 4


def test_checkpoint_provenance_does_not_hash_backings_or_launch_qemu_img(suite, monkeypatch):
    lease, _ = suite
    with lease:
        lease.prepare()
        with monkeypatch.context() as patch:
            info = Mock(side_effect=AssertionError('unexpected qemu-img'))
            audit = Mock(side_effect=AssertionError('unexpected full audit'))
            patch.setattr(lease.commands, 'info', info)
            patch.setattr(lease.capture, 'verify_snapshot', audit)
            for _ in range(3):
                assert lease.verify_baseline() == lease.capture.state['proof']
    lease.audit()


@pytest.mark.parametrize('fault', ['instance', 'tag', 'snapshot', 'lock', 'disk'])
def test_changed_ownership_refuses_force_restore(suite, fault):
    lease, current = suite
    with pytest.raises(RuntimeError) if fault == 'lock' else nullcontext(), lease:
        lease.prepare()
        lease.start()
        saved = dict(current)
        metadata = lease.source.baseline_xml
        disk = lease.source.layout['disk']
        if fault == 'instance':
            current['id'] += 1
        elif fault == 'tag':
            current['xml'] = current['xml'].replace(lease.state['run'], 'b' * 32)
        elif fault == 'snapshot':
            lease.source.baseline_xml += ' '
        elif fault == 'lock':
            fcntl.flock(lease.fd, fcntl.LOCK_UN)
        else:
            lease.source.layout['disk'] += '-replacement'
        before = lease.source.domain.revertToSnapshot.call_count
        try:
            with pytest.raises(RuntimeError):
                lease.stop()
            assert lease.source.domain.revertToSnapshot.call_count == before
        finally:
            current.update(saved)
            lease.source.baseline_xml = metadata
            lease.source.layout['disk'] = disk
    if fault != 'lock':
        lease.audit()
    else:
        with pytest.raises(RuntimeError, match='backing-owner-changed'):
            system.Lease.release(lease)
        assert lease.fd is None


def test_failed_case_is_restored_but_cannot_start_another_case(suite):
    lease, _ = suite
    with pytest.raises(ValueError, match='case failed'):
        with lease:
            lease.prepare()
            lease.start()
            raise ValueError('case failed')
    assert lease.state['phase'] == 'complete'
    before = lease.source.domain.create.call_count
    with pytest.raises(RuntimeError, match='previous-case-incomplete'):
        lease.__enter__()
    assert lease.source.domain.create.call_count == before
    lease.audit()
    assert lease.fd is None


@pytest.mark.parametrize('worker_stops', [False, True])
def test_restore_failure_is_not_retried_by_cleanup_or_final_audit(suite, worker_stops):
    lease, _ = suite
    with pytest.raises(RuntimeError, match='restore failed'):
        with lease:
            lease.prepare()
            lease.start()
            lease.source.domain.revertToSnapshot.side_effect = RuntimeError('restore failed')
            if worker_stops:
                lease.stop()
    before = lease.source.domain.revertToSnapshot.call_count
    assert before == 2  # Initial baseline and exactly one failed final revert.
    with pytest.raises(RuntimeError, match='cleanup-incomplete'):
        lease.audit()
    assert lease.source.domain.revertToSnapshot.call_count == before
    assert lease.fd is None


@pytest.mark.parametrize('fault', ['backing', 'guest', 'state'])
def test_final_audit_refuses_mutation_and_releases_lock(suite, fault):
    lease, _ = suite
    run_case(lease)
    if fault == 'backing':
        lease.capture.anchor.write_bytes(b'changed backing bytes')
    elif fault == 'guest':
        lease.inspect.return_value = {'changed': True}
    else:
        lease.capture.read_state = Mock(return_value={'changed': True})
    with pytest.raises(RuntimeError):
        lease.audit()
    assert lease.fd is None


def test_source_validation_runs_after_audit_before_release_and_failure_is_terminal(suite):
    lease, _ = suite
    run_case(lease)
    def validate():
        assert lease.fd is not None
        assert lease.capture.verification_totals['calls'] == 2
        assert lease.verify_baseline() == lease.capture.state['proof']
        raise ValueError('source changed during audit')
    with pytest.raises(ValueError, match='source changed'):
        lease.audit(validate=validate)
    assert lease.fd is None


@pytest.mark.parametrize('failure', [None, 'audit', 'host', 'close'])
def test_suite_closes_connection_even_after_audit_or_host_failure(monkeypatch, failure):
    suite = suite_lease.Suite(Mock())
    suite.source = Mock()
    suite.lease = Mock()
    suite.host_before = 'original'
    fingerprint = Mock(return_value='changed' if failure == 'host' else 'original')
    monkeypatch.setattr(system, 'host_fingerprint', fingerprint)
    if failure == 'audit':
        suite.lease.audit.side_effect = RuntimeError('audit failed')
    elif failure == 'close':
        suite.source.close.side_effect = RuntimeError('close failed')
    with pytest.raises(RuntimeError) if failure else nullcontext():
        suite.close()
    suite.lease.audit.assert_called_once()
    suite.source.close.assert_called_once()


@pytest.fixture
def snapshots(suite):
    lease, current = suite
    domain = lease.source.domain
    baseline = domain.snapshotLookupByName.return_value
    # The baseline fixture may use its supported historical snapshot name.
    lease.capture.directory_identity = lease.capture.private_directory()
    baseline_name = lease.capture.read_state()['proof']['name']
    names = {baseline_name: baseline}
    events = []
    def add(name, xml):
        snap = Mock()
        snap.getXMLDesc.return_value = xml
        def delete(flags):
            assert flags == 0 and lease.source.off
            events.append(('delete', name))
            del names[name]
        snap.delete.side_effect = delete
        names[name] = snap
        return snap
    def lookup(name, flags):
        if name not in names:
            raise RuntimeError('suite:installed-snapshot-missing')
        return names[name]
    restore = domain.revertToSnapshot.side_effect
    def revert(snap, flags):
        name = next(name for name, value in names.items() if value is snap)
        events.append(('restore', name))
        restore(snap, flags)
    def create(xml, flags):
        assert lease.source.off and current['xml'] == lease.original_xml
        assert flags == 0
        root = ET.fromstring(xml)
        assert root.find('memory').get('snapshot') == 'no'
        name = root.findtext('name')
        assert name not in names
        events.append(('create', name))
        return add(name, xml)
    domain.snapshotLookupByName.side_effect = lookup
    domain.snapshotListNames.side_effect = lambda flags: list(names)
    domain.revertToSnapshot.side_effect = revert
    domain.snapshotCreateXML.side_effect = create
    return lease, names, events, add, baseline_name


@pytest.fixture
def prepared_suite(snapshots, tmp_path, monkeypatch):
    import installed_setup
    import provenance
    import vm_transport
    lease, names, events, add, baseline_name = snapshots
    owner = suite_lease.Suite(Mock())
    owner.lease = lease
    owner.guestfs = Mock()
    owner.commands = Mock()
    owner.commands.run.return_value = b'1.1+test~26.04\n'
    monkeypatch.setattr(installed_setup, 'stage', Mock())
    monkeypatch.setattr(system, 'bootstrap', Mock(return_value='ssh-ed25519 fixture'))
    monkeypatch.setattr(system, 'address', Mock(return_value='fixture-host'))
    monkeypatch.setattr(provenance, 'VerifiedInputs', Mock())
    monkeypatch.setattr(vm_transport, 'Transport', Mock())
    setup = Mock()
    setup.run.side_effect = lambda *args, **kwargs: events.append(('install-reboot', kwargs['verify']))
    monkeypatch.setattr(installed_setup, 'InstalledSetup', Mock(return_value=setup))
    return owner, tmp_path, setup, snapshots


@pytest.mark.parametrize('stale', [False, True])
def test_installed_suite_installs_once_and_restores_next_case_without_extra_audits(prepared_suite, stale):
    owner, directory, setup, (lease, names, events, add, baseline_name) = prepared_suite
    name = 'onpc-v1.1'
    if stale:
        add(name, '<stale/>')
    installed = {'preconditions': ['installed-digest-verified-product']}
    clean = {'preconditions': ['accepted-product-free-baseline']}
    cases = [installed, installed, clean, installed]
    for index, case in enumerate(cases):
        owner.next_case = cases[index + 1] if index + 1 < len(cases) else None
        lease.ledger = system.RunLedger()
        with lease:
            owner.prepare_case(case, directory, directory, {}, root=directory)
            assert lease._restored_name == (name if case is installed else baseline_name)
            lease.start()
            lease.stop()
        assert lease.capture.verification_totals['calls'] == 1
        assert lease.inspect.call_count == 1
    if stale:
        setup.run.assert_not_called()
    else:
        setup.run.assert_called_once_with(lease.guard, verify=False)
    assert [event for event in events if event[0] == 'restore'] == [
        ('restore', baseline_name), ('restore', name), ('restore', name),
        ('restore', baseline_name), ('restore', name), ('restore', baseline_name)]
    lease.audit()
    assert name in names and baseline_name in names
    assert not [event for event in events if event[0] == 'delete']
    assert lease.capture.verification_totals['calls'] == 2
    assert lease.inspect.call_count == 2
    lease.source.domain.destroyFlags.assert_not_called()


def test_suite_progress_precedes_slow_operations(prepared_suite, monkeypatch):
    owner, directory, setup, (lease, names, events, add, baseline_name) = prepared_suite
    progress = MagicMock()
    monkeypatch.setattr(system, 'watch_progress', progress)
    name = 'onpc-v1.1'
    add(name, '<stale/>')
    originals = {}
    for method, label in (
            ('prepare', 'Restoring onpc-baseline'),
            ('delete_installed', 'Deleting existing snapshot ' + name + ' (overwrite=true)'),
            ('create_installed', 'Taking snapshot ' + name)):
        original = getattr(lease, method)
        originals[method] = original
        def checked(*args, original=original, label=label, **kwargs):
            progress.suite_preparation.assert_called_with(label)
            return original(*args, **kwargs)
        monkeypatch.setattr(lease, method, checked)
    setup.run.side_effect = lambda *args, **kwargs: (
        progress.suite_preparation.assert_called_with('Installing app'))
    with lease:
        owner.prepare_installed(directory, directory, {}, root=directory)
        progress.suite_prepared.assert_called_once_with()
        assert [call.args[0] for call in progress.suite_preparation.call_args_list] == [
            'Restoring onpc-baseline', 'Deleting existing snapshot ' + name + ' (overwrite=true)',
            'Installing app', 'Taking snapshot ' + name]
    for method, original in originals.items():
        monkeypatch.setattr(lease, method, original)
    lease.audit()


def test_every_snapshot_mutation_reserves_footer_before_libvirt(prepared_suite, monkeypatch):
    owner, directory, setup, (lease, names, events, add, baseline_name) = prepared_suite
    progress = Progress([dict(case_id='first', coverage_id=1, title='First'),
                         dict(case_id='next', coverage_id=2, title='Next'),
                         dict(case_id='last', coverage_id=3, title='Last')])
    progress.prepare('first')
    monkeypatch.setattr(system, 'watch_progress', progress)
    published = []
    progress.publish_progress = lambda: published.append(progress.snapshot(display=True))
    observed = []

    def checked(action, name, original, *args):
        label = f'{action} snapshot "{name}"'
        shown = progress.snapshot(display=True)
        assert published[-1]['operation'] == shown['operation'] == label
        started = shown['operation_started_ns']
        system.log('stage:other-controller-output')
        progress.operation('Unrelated worker preparation')
        shown = progress.snapshot(display=True)
        assert progress_text({'progress': shown}, now_ns=started + 61_000_000_000)[2] == (
            label + ' - (1m 1s)')
        result = original(*args)
        assert progress.snapshot(display=True)['operation'] == label
        observed.append((action, name, shown['current']))
        return result

    def watch_delete(name, snap):
        original = snap.delete.side_effect
        snap.delete.side_effect = lambda flags: checked('Deleting', name, original, flags)

    domain = lease.source.domain
    restore = domain.revertToSnapshot.side_effect
    domain.revertToSnapshot.side_effect = lambda snap, flags: checked('Restoring',
        next(name for name, value in names.items() if value is snap), restore, snap, flags)
    create = domain.snapshotCreateXML.side_effect
    def watch_create(xml, flags):
        name = ET.fromstring(xml).findtext('name')
        snap = checked('Taking', name, create, xml, flags)
        watch_delete(name, snap)
        return snap
    domain.snapshotCreateXML.side_effect = watch_create
    name = 'onpc-v1.1'
    watch_delete(name, add(name, '<stale/>'))
    installed = {'preconditions': ['installed-digest-verified-product']}
    clean = {'preconditions': ['accepted-product-free-baseline']}
    cases = (installed, installed, clean)
    for index, case in enumerate(cases):
        owner.next_case = cases[index + 1] if index + 1 < len(cases) else None
        lease.ledger = system.RunLedger()
        with lease:
            owner.prepare_case(case, directory, directory, {}, root=directory)
            lease.start()
            if owner.next_case is not None:
                progress.prepare_next()
            lease.stop()
        if owner.next_case is not None:
            progress.prepare(progress.cases[index + 1]['case_id'])
    lease.audit()
    assert observed == [
        ('Restoring', baseline_name, 1),
        ('Restoring', name, 1), ('Restoring', name, 2),
        ('Restoring', baseline_name, 3), ('Restoring', baseline_name, 3)]
    assert progress.snapshot_value is None


def test_overwrite_false_existing_snapshot_is_a_logged_noop(prepared_suite, capsys):
    owner, directory, setup, (lease, names, events, add, baseline_name) = prepared_suite
    name = 'onpc-v1.1'
    existing = add(name, '<existing/>')
    with lease:
        assert owner.prepare_installed(directory, directory, {}, root=directory,
                                       overwrite=False) is False
        assert not lease.mutated
        assert lease.installed_name is None
        assert 'e2e_snapshot' not in lease.state
    lease.audit(retain_installed=True)
    assert events == []
    assert names[name] is existing and baseline_name in names
    assert not (directory / 'suite-setup').exists()
    setup.run.assert_not_called()
    assert 'Keeping existing snapshot ' + name in capsys.readouterr().err


@pytest.mark.parametrize('overwrite', [False, True])
def test_missing_current_version_is_created_and_other_versions_preserved(prepared_suite, overwrite):
    owner, directory, setup, (lease, names, events, add, baseline_name) = prepared_suite
    unrelated = add('onpc-0.9', '<unrelated/>')
    with lease:
        assert owner.prepare_installed(directory, directory, {}, root=directory,
                                       overwrite=overwrite) is True
    lease.audit(retain_installed=True)
    assert 'onpc-v1.1' in names
    assert names['onpc-0.9'] is unrelated and baseline_name in names
    assert 'e2e_snapshot' not in lease.state
    assert lease.state['phase'] == 'complete' and lease.fd is None
    assert lease.source.off and lease._restored_name == 'onpc-v1.1'
    assert lease.capture.verification_totals['calls'] == 2
    setup.run.assert_called_once_with(lease.guard, verify=False)
    assert not [event for event in events if event[0] == 'delete']


def test_failed_final_provenance_check_preserves_snapshot_and_restores_baseline(prepared_suite):
    owner, directory, setup, (lease, names, events, add, baseline_name) = prepared_suite
    with lease:
        owner.prepare_installed(directory, directory, {}, root=directory)
    with pytest.raises(ValueError, match='changed'):
        lease.audit(retain_installed=True,
                    validate=Mock(side_effect=ValueError('changed')))
    assert lease.fd is None
    assert 'e2e_snapshot' not in lease.state
    assert 'onpc-v1.1' in names
    assert lease._restored_name == baseline_name


@pytest.mark.parametrize('fault', ['install', 'snapshot-create', 'case'])
def test_suite_failure_restores_baseline_and_preserves_installed_snapshot(prepared_suite, fault):
    owner, directory, setup, (lease, names, events, add, baseline_name) = prepared_suite
    installed = {'preconditions': ['installed-digest-verified-product']}
    owner.next_case = installed
    if fault == 'install':
        setup.run.side_effect = RuntimeError('injected failure')
    if fault == 'snapshot-create':
        create = lease.source.domain.snapshotCreateXML.side_effect
        def fail(*args):
            create(*args)  # libvirt can create metadata before an RPC fails.
            raise RuntimeError('injected failure')
        lease.source.domain.snapshotCreateXML.side_effect = fail
    with pytest.raises(RuntimeError, match='injected failure'):
        with lease:
            owner.prepare_case(installed, directory, directory, {}, root=directory)
            lease.start()
            raise RuntimeError('injected failure')
    lease.audit()
    assert baseline_name in names
    assert ('onpc-v1.1' in names) == (fault != 'install')
    assert not [event for event in events if event[0] == 'delete']
    assert lease._restored_name == baseline_name
    assert lease.fd is None


def test_missing_installed_snapshot_stops_without_reinstall_or_restore_retry(prepared_suite):
    owner, directory, setup, (lease, names, events, add, baseline_name) = prepared_suite
    installed = {'preconditions': ['installed-digest-verified-product']}
    owner.next_case = installed
    with pytest.raises(RuntimeError, match='installed-snapshot-missing'):
        with lease:
            owner.prepare_case(installed, directory, directory, {}, root=directory)
            lease.start()
            del names[lease.installed_name]
            lease.stop()
    before = list(events)
    with pytest.raises(RuntimeError, match='cleanup-incomplete'):
        lease.audit()
    assert events == before and setup.run.call_count == 1
    assert lease.fd is None


@pytest.mark.parametrize('name', ['onpc-1.1', 'onpc-baseline', '../onpc-1.1', 'other-1.1'])
def test_interrupted_suite_recovery_only_deletes_journaled_version(snapshots, name):
    lease, names, events, add, baseline_name = snapshots
    lease.__enter__()
    lease.prepare()
    lease.state['e2e_snapshot'] = name
    lease.save('isolated')
    if name != baseline_name:
        add(name, '<snapshot/>')
    system.Lease.release(lease)  # Simulate controller exit before starting a case.
    recovery = system.Lease(lease.source, lease.commands, lease.inspect,
        directory=lease.directory, anchor=lease.capture.anchor, graphics_type='vnc')
    before = list(events)
    if name == 'onpc-1.1':
        recovery.recover_graphical_cleanup()
        assert events[len(before):] == [('restore', baseline_name), ('delete', name)]
        assert recovery.state['phase'] == 'complete'
    else:
        with pytest.raises(RuntimeError, match='snapshot-identity'):
            recovery.recover_graphical_cleanup()
        assert events == before
    assert baseline_name in names
    assert recovery.fd is None


def test_inventory_package_lifecycle_cases_use_clean_baseline():
    import json
    from tests.support.paths import ROOT
    inventory = json.loads((ROOT / 'tests/e2e/scenarios.json').read_text())
    families = {family['id']: family for family in inventory['scenarios']}
    clean_baseline = {'E2E-001', 'E2E-002', 'E2E-026', 'E2E-027'}
    assert clean_baseline <= families.keys()
    for name in clean_baseline:
        assert not suite_lease.needs_installed(families[name])
    for name in families.keys() - clean_baseline:
        assert suite_lease.needs_installed(families[name])


def test_no_ready_provider_case_is_dispatched_to_snapshot_setup(prepared_suite):
    import inventory
    owner, directory, setup, (lease, names, events, add, baseline_name) = prepared_suite
    document, _ = inventory.read_json(inventory.INVENTORY)
    for family in document['scenarios']:
        for variant in family['variants']:
            variant.update(status='pending', executable=None,
                           pending_reason='Unqualified provider fixture')
    cases = inventory.resolve_selection(document, ready_only=True)['cases']
    assert cases == []
    with pytest.raises(inventory.InventoryError, match='selection:no-ready-cases'):
        inventory.resolve_selection(document, ready_only=True, require_runnable=True)
    setup.run.assert_not_called()
    assert [event for event in events if event[0] == 'restore'] == []
    assert set(names) == {baseline_name}


def test_wrong_transition_snapshot_refuses_before_case_provisioning(prepared_suite):
    owner, directory, setup, (lease, names, events, add, baseline_name) = prepared_suite
    installed = {'preconditions': ['installed-digest-verified-product']}
    # A scheduler that forgot the next installed case restores baseline.
    with lease:
        owner.prepare_case(installed, directory, directory, {}, root=directory)
        lease.start()
        lease.stop()
    assert lease._restored_name == baseline_name
    with pytest.raises(RuntimeError, match='case-snapshot-not-restored'):
        with lease:
            owner.prepare_case(installed, directory, directory, {}, root=directory)
    setup.run.assert_called_once()
    lease.audit()
