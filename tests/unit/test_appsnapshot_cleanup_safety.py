"""Standalone entry points cannot bypass validation, ownership or failed setup."""
from contextlib import nullcontext
import runpy
from unittest.mock import Mock

import pytest

import cleanup_e2e
import prepare_appsnapshot as launcher
import test_recovery
import prepare_snapshot as controller
from tests.support.paths import ROOT


@pytest.mark.parametrize('version', ['1.1', '1.1+ppa1~ubuntu26.04.1',
    '1.1-ppa1-ubuntu26.04.1', '1.1+ppa2~ubuntu26.04.1'])
def test_snapshot_name_uses_app_release(version):
    assert controller.snapshot_name(version) == 'onpc-v1.1'


def test_snapshot_name_preserves_release_components():
    assert controller.snapshot_name('1.12.3+ppa1~ubuntu26.04.1') == 'onpc-v1.12.3'


@pytest.mark.parametrize('argv, expected', [([], 'true'), (['--overwrite'], 'true'),
    (['--overwrite', 'true'], 'true'), (['--overwrite', 'false'], 'false'),
    (['--overwrite=false'], 'false')])
def test_overwrite_defaults_and_explicit_values(argv, expected):
    assert launcher.arguments(argv).overwrite == expected


@pytest.mark.parametrize('argv', [['--overwrite', 'yes'], ['--overwrite='],
    ['--overwrite', 'FALSE'], ['--over', 'false'], ['--snapshot', 'onpc-1.1']])
def test_invalid_options_refused_before_any_work(argv, monkeypatch):
    check = Mock(side_effect=AssertionError('authorization attempted'))
    monkeypatch.setattr(launcher, 'check', check)
    with pytest.raises(SystemExit) as error:
        launcher.main(argv)
    assert error.value.code == 2
    check.assert_not_called()


@pytest.fixture
def launch(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, '__file__', str(tmp_path / 'tools/prepare_appsnapshot.py'))
    monkeypatch.setattr(launcher.os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(launcher.test_activity, 'activity', lambda _: nullcontext())
    monkeypatch.setattr(launcher, 'check', Mock())
    cleanup = Mock(return_value=0)
    monkeypatch.setattr(launcher, 'cleanup', cleanup)
    controller = Mock()
    controller.installed.return_value = nullcontext(controller)
    controller.stopped.is_set.return_value = False
    monkeypatch.setattr(launcher, 'Control', lambda: controller)
    allocation = Mock(return_value=str(tmp_path / 'artifacts'))
    monkeypatch.setattr(launcher.tempfile, 'mkdtemp', allocation)
    store = Mock()
    store.session.return_value = nullcontext('a' * 32)
    monkeypatch.setattr(launcher.test_retention, 'Store', lambda _: store)
    monkeypatch.setattr(launcher.test_retention, 'allocate', lambda factory, **kw: factory(**kw))
    return controller, cleanup, allocation


@pytest.mark.parametrize('status', [0, 1, 2, 130])
def test_probe_success_or_failure_never_cleans_builds_or_installs(launch, status):
    control, cleanup, allocation = launch
    control.run.return_value = status
    assert launcher.main(['--overwrite', 'false']) == status
    assert control.run.call_args.args[0][-2:] == ['appsnapshot', '--probe']
    control.run.assert_called_once()
    cleanup.assert_not_called()
    allocation.assert_not_called()


@pytest.mark.parametrize('argv, results, calls', [([], [0, 0], 2),
    (['--overwrite'], [0, 0], 2), (['--overwrite', 'false'], [3, 0, 0], 3)])
def test_needed_preparation_cleans_builds_and_passes_overwrite(launch, argv, results, calls):
    control, cleanup, allocation = launch
    control.run.side_effect = results
    assert launcher.main(argv) == 0
    cleanup.assert_called_once()
    allocation.assert_called_once()
    assert control.run.call_count == calls
    command = control.run.call_args.args[0]
    assert command[1] == '--disable-internal-agent'
    assert '--retention-run=' + 'a' * 32 in command
    assert command[4:7] == ['--unattended', 'appsnapshot', '--overwrite']
    assert command[7] == ('false' if 'false' in argv else 'true')
    assert control.run.call_args.kwargs['cooperative'] is True


def test_failed_cleanup_does_not_build_or_install(launch):
    control, cleanup, allocation = launch
    cleanup.side_effect = ValueError('cleanup refused')
    assert launcher.main([]) == 2
    allocation.assert_not_called()
    control.run.assert_not_called()


def test_failed_build_does_not_install(launch):
    control, cleanup, allocation = launch
    control.run.return_value = 17
    assert launcher.main([]) == 17
    control.run.assert_called_once()
    assert control.run.call_args.args[0][2].endswith('/tools/build_test_artifacts.py')


def test_cleanup_requires_checkout_ownership(tmp_path, monkeypatch):
    monkeypatch.setattr(test_recovery.test_activity, 'descriptors', lambda: ())
    with pytest.raises(ValueError, match='ownership required'):
        test_recovery.cleanup(tmp_path)


def test_standalone_cleanup_uses_the_shared_module_under_activity(tmp_path, monkeypatch):
    monkeypatch.setattr(cleanup_e2e, '__file__', str(tmp_path / 'tools/cleanup_e2e.py'))
    monkeypatch.setattr(cleanup_e2e.os, 'geteuid', lambda: 1000)
    def cleanup(root):
        assert root == tmp_path
        assert cleanup_e2e.test_activity.descriptors()
        return 7
    monkeypatch.setattr(cleanup_e2e, 'cleanup', cleanup)
    assert cleanup_e2e.main([]) == 7


@pytest.fixture
def dispatch():
    module = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))
    select = module['selection']
    select.__globals__['VM_UUID'] = 'pinned-test-uuid'
    return select


def test_snapshot_dispatch_pins_vm_and_confines_inputs(dispatch, tmp_path):
    assert dispatch(ROOT, ['appsnapshot', '--probe'])[-3:] == [
        '--expected-uuid', 'pinned-test-uuid', '--probe']
    with pytest.raises(ValueError):
        dispatch(ROOT, ['appsnapshot', '--artifacts', '/etc'])
    with pytest.raises(ValueError):
        dispatch(ROOT, ['appsnapshot', '--probe', '--artifacts', str(tmp_path)])
    with pytest.raises(ValueError):
        dispatch(ROOT, ['appsnapshot', '--expected-uuid', 'other'])
    dispatch.__globals__['VM_UUID'] = None
    with pytest.raises(ValueError, match='prepare-baseline'):
        dispatch(ROOT, ['appsnapshot', '--probe'])


@pytest.mark.parametrize('exists', [False, True])
def test_probe_uses_exclusive_vm_lock_and_never_mutates(tmp_path, monkeypatch, exists):
    import fcntl
    import os
    base = controller.system.baseline
    lock = tmp_path / 'baseline.lock'
    lock.touch(mode=0o600)
    monkeypatch.setattr(base, 'BASELINES', tmp_path)
    monkeypatch.setattr(base, 'canonical', Mock())
    monkeypatch.setattr(base, 'identity', Mock())
    monkeypatch.setattr(base, 'baseline_lock_path', lambda _: lock)
    monkeypatch.setattr(controller, 'current_name', lambda _: 'onpc-1.1')
    source = Mock()
    monkeypatch.setattr(controller, 'open_source', lambda: (source, Mock()))
    monkeypatch.setattr(controller, 'check_identity', Mock())
    def names(flags):
        other = os.open(lock, os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(other)
        return ['onpc-1.1'] if exists else ['onpc-0.9']
    source.domain.snapshotListNames.side_effect = names
    assert controller.probe('pinned') == (0 if exists else 3)
    source.domain.snapshotListNames.assert_called_once_with(0)
    assert len(source.domain.mock_calls) == 1
    source.close.assert_called_once()
    assert list(tmp_path.iterdir()) == [lock]
    with lock.open() as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_probe_rejects_foreign_vm_before_reading_snapshots(tmp_path, monkeypatch):
    base = controller.system.baseline
    lock = tmp_path / 'baseline.lock'
    lock.touch(mode=0o600)
    monkeypatch.setattr(base, 'BASELINES', tmp_path)
    monkeypatch.setattr(base, 'canonical', Mock())
    monkeypatch.setattr(base, 'identity', Mock())
    monkeypatch.setattr(base, 'baseline_lock_path', lambda _: lock)
    monkeypatch.setattr(controller, 'current_name', lambda _: 'onpc-1.1')
    source = Mock()
    monkeypatch.setattr(controller, 'open_source', lambda: (source, Mock()))
    monkeypatch.setattr(controller, 'check_identity', Mock(side_effect=ValueError('foreign VM')))
    with pytest.raises(ValueError, match='foreign VM'):
        controller.probe('pinned')
    source.domain.snapshotListNames.assert_not_called()
    source.close.assert_called_once()
