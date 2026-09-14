"""Only the inherited lock capability can join an active aggregate."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

import test_activity
import regression_inputs


def child(tmp_path, env, pass_fds=(), *, cleanup=False):
    script = tmp_path / 'lock_child.py'
    script.write_text('''import pathlib,sys
sys.path.insert(0, sys.argv[1])
import test_activity
import regression_inputs
regression_inputs.identity = lambda root: 'a' * 64
try:
    with test_activity.activity(pathlib.Path(sys.argv[2])):
        print(test_activity.cleanup_verified(pathlib.Path(sys.argv[2])) if sys.argv[3] == 'cleanup' else 'owned')
except (ValueError, OSError) as error:
    print(type(error).__name__)
    sys.exit(2)
''')
    return subprocess.run([sys.executable, '-B', str(script),
                           str(Path(test_activity.__file__).parent), str(tmp_path / 'checkout'),
                           'cleanup' if cleanup else 'ownership'],
                          env=env, pass_fds=pass_fds, capture_output=True, text=True, timeout=10)


def test_competing_process_refuses_then_succeeds_after_owner_exits(tmp_path):
    env = os.environ.copy()
    env.pop(test_activity.VARIABLE, None)
    with test_activity.activity(tmp_path / 'checkout'):
        assert child(tmp_path, env).returncode == 2
    assert child(tmp_path, env).returncode == 0


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


@pytest.mark.parametrize('payload', [b'not-a-digest', b'a' * 65, b'\xff' * 64, b'b' * 64])
def test_cleanup_gate_refuses_invalid_or_changed_source(tmp_path, monkeypatch, payload):
    monkeypatch.setattr(regression_inputs, 'identity', lambda root: 'a' * 64)
    with test_activity.activity(tmp_path / 'checkout'):
        descriptor, = test_activity.descriptors()
        os.pwrite(descriptor, payload, 0)
        with pytest.raises(ValueError, match='no longer match'):
            test_activity.cleanup_verified(tmp_path / 'checkout')
