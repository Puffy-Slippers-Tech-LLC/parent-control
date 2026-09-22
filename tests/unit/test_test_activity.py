"""Only the inherited lock capability can join an active aggregate."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

import test_activity
import regression_inputs


def child(tmp_path, env, pass_fds=(), *, cleanup=False, host_only=None, retention=False):
    script = tmp_path / 'lock_child.py'
    script.write_text('''import pathlib,sys
sys.path.insert(0, sys.argv[1])
import test_activity
import regression_inputs
import test_retention
regression_inputs.identity = lambda root: 'a' * 64
try:
    root = pathlib.Path(sys.argv[2])
    scope = {'auto': None, 'host': True, 'vm': False}[sys.argv[4]]
    with test_activity.activity(root, host_only=scope):
        if sys.argv[5] == 'retain':
            with test_retention.Store(test_activity.retention_path(root)).session():
                pass
        print(test_activity.cleanup_verified(pathlib.Path(sys.argv[2])) if sys.argv[3] == 'cleanup' else 'owned')
except (ValueError, OSError) as error:
    print(type(error).__name__)
    sys.exit(2)
''')
    return subprocess.run([sys.executable, '-B', str(script),
                           str(Path(test_activity.__file__).parent), str(tmp_path / 'checkout'),
                           'cleanup' if cleanup else 'ownership',
                           'auto' if host_only is None else 'host' if host_only else 'vm',
                           'retain' if retention else 'none'],
                          env=env, pass_fds=pass_fds, capture_output=True, text=True, timeout=10)


def test_competing_process_refuses_then_succeeds_after_owner_exits(tmp_path):
    env = os.environ.copy()
    env.pop(test_activity.VARIABLE, None)
    with test_activity.activity(tmp_path / 'checkout'):
        assert child(tmp_path, env).returncode == 2
    assert child(tmp_path, env).returncode == 0


@pytest.mark.parametrize('host_only', [False, True])
def test_host_and_vm_owners_and_retention_can_overlap(tmp_path, host_only):
    import test_retention
    root = tmp_path / 'checkout'
    with test_activity.activity(root, host_only=host_only):
        with test_retention.Store(test_activity.retention_path(root)).session():
            assert child(tmp_path, {}, host_only=host_only).returncode == 2
            assert child(tmp_path, {}, host_only=not host_only, retention=True).returncode == 0
            inherited = child(tmp_path, test_activity.environment(), test_activity.descriptors())
            assert inherited.returncode == 0
            # A real descriptor cannot be reused for the other ownership scope.
            assert child(tmp_path, test_activity.environment(), test_activity.descriptors(),
                         host_only=not host_only).returncode == 2


def test_owned_child_can_join_but_environment_alone_cannot(tmp_path):
    with test_activity.activity(tmp_path / 'checkout'):
        env = os.environ | test_activity.environment()
        result = child(tmp_path, env, test_activity.descriptors())
        assert result.returncode == 0 and result.stdout.strip() == 'owned'
        assert child(tmp_path, env).returncode == 2
        # Joining must not unlock the parent's open file description.
        assert child(tmp_path, {}).returncode == 2


def test_foreign_descriptor_and_symlink_refuse(tmp_path, monkeypatch):
    other = tmp_path / 'unrelated'
    other.write_text('preserve')
    with other.open() as stream:
        monkeypatch.setenv(test_activity.VARIABLE, str(stream.fileno()))
        with pytest.raises(ValueError, match='foreign'):
            with test_activity.activity(tmp_path / 'checkout'):
                pytest.fail('must refuse')
    monkeypatch.delenv(test_activity.VARIABLE)
    target = tmp_path / 'checkout/artifacts/test-activity/lock'
    target.unlink()
    target.symlink_to(other)
    with pytest.raises(OSError):
        with test_activity.activity(tmp_path / 'checkout'):
            pytest.fail('must refuse')
    assert other.read_text() == 'preserve'


def test_cleanup_gate_requires_inherited_lock_and_expires_with_activity(tmp_path, monkeypatch):
    monkeypatch.delenv(test_activity.VARIABLE, raising=False)
    root = tmp_path / 'checkout'
    assert not test_activity.cleanup_verified(root)
    with test_activity.activity(root):
        env = os.environ | test_activity.environment()
        fds = test_activity.descriptors()
        assert child(tmp_path, env, fds, cleanup=True).stdout.strip() == 'False'
        test_activity.record_cleanup('a' * 64)
        assert child(tmp_path, env, fds, cleanup=True).stdout.strip() == 'True'
        assert child(tmp_path, env, cleanup=True).returncode == 2
        assert child(tmp_path, {}, cleanup=True).returncode == 2
    # A persisted success record cannot bypass a fresh command's safety suite.
    assert child(tmp_path, {}, cleanup=True).stdout.strip() == 'False'


def test_parallel_cleanup_command_inherits_current_host_activity(tmp_path):
    import regression_process
    root = tmp_path / 'checkout'
    with test_activity.activity(root, host_only=True):
        descriptor, = test_activity.descriptors()
        command = regression_process.safety_command(root)
    assert command == ['/usr/bin/python3', '-B',
                       str(root / 'tools/regression_process.py'),
                       '--cleanup-prerequisites', f'--activity-fd={descriptor}']


def test_parallel_cleanup_coordinator_joins_and_restores_activity(tmp_path, monkeypatch, capsys):
    import e2e_startup_cache
    import regression
    import regression_process
    from regression_selection import CLEANUP_SELECTION
    root = tmp_path / 'checkout'
    monkeypatch.setattr(e2e_startup_cache, 'qualified_cleanup', lambda root, run: run())
    monkeypatch.delenv(test_activity.VARIABLE, raising=False)
    with test_activity.activity(root, host_only=True):
        descriptor, = test_activity.descriptors()
        original_output = sys.stdout

        def retained(selected_root, *, selections):
            assert selected_root == root
            assert test_activity.descriptors() == (descriptor,)
            assert selections == [(CLEANUP_SELECTION, [])]
            assert isinstance(sys.stdout, regression_process.PipeFrameOutput)
            sys.stdout.frame(['intermediate cleanup frame',
                              '\033[97;1mOverall - 42% (42/100) - 5s\033[0m'])
            print('final cleanup output')
            return 7

        monkeypatch.setattr(regression, 'retained_main', retained)
        assert regression_process.cleanup_main(root, activity_fd=descriptor) == 7
        assert test_activity.descriptors() == (descriptor,)
        assert test_activity.VARIABLE not in os.environ
        assert sys.stdout is original_output
    lines = capsys.readouterr().out.splitlines()
    import json
    assert json.loads(lines[0].removeprefix(regression_process.FRAME_PREFIX)) == [
        'intermediate cleanup frame', '\033[97;1mOverall - 42% (42/100) - 5s\033[0m']
    assert lines[1] == regression_process.FRAME_PREFIX + '[]'
    assert lines[2:] == ['final cleanup output']


@pytest.mark.parametrize('payload', [b'not-a-digest', b'a' * 65, b'\xff' * 64])
def test_cleanup_gate_refuses_invalid_record(tmp_path, monkeypatch, payload):
    monkeypatch.setattr(regression_inputs, 'identity', lambda root: 'a' * 64)
    with test_activity.activity(tmp_path / 'checkout'):
        descriptor, = test_activity.descriptors()
        os.pwrite(descriptor, payload, 0)
        with pytest.raises(ValueError, match='invalid aggregate cleanup'):
            test_activity.cleanup_verified(tmp_path / 'checkout')


def test_cleanup_gate_survives_checkout_edits_without_rescanning(tmp_path, monkeypatch):
    monkeypatch.setattr(regression_inputs, 'identity', lambda _: pytest.fail('must not rescan'))
    root = tmp_path / 'checkout'
    with test_activity.activity(root):
        target = root / 'test.py'
        target.write_text('before')
        test_activity.record_cleanup('a' * 64)
        target.write_text('after')
        assert test_activity.cleanup_verified(root)
        assert child(tmp_path, os.environ | test_activity.environment(),
                     test_activity.descriptors(), cleanup=True).stdout.strip() == 'True'
