"""Preapproved release operations cannot become arbitrary command/path grants."""
from pathlib import Path
import runpy
import subprocess

import pytest

from tests.support.paths import ROOT


@pytest.mark.parametrize('args', [
    ['upload'], ['sign'], ['push'], ['status', '--command', 'id'],
    ['prepare', '/tmp/unrelated'], ['prepare', '/etc/onpc-release-test'],
    ['prepare', '/tmp/onpc-release-test/source'],
    ['prepare', '/tmp/onpc-release-test/../onpc-release-other'],
    ['inspect', '/tmp/onpc-release-test'],
    ['check-build', '/tmp/onpc-release-test/source', '--enable-network'],
    ['check-build', '/tmp/onpc-release-test/source', '--debbuildopt=-d'],
    ['inspect', '/tmp/onpc-release-test/source', '--shell'],
])
def test_invalid_operations_are_rejected_before_implementation_is_loaded(args, monkeypatch):
    launcher = runpy.run_path(str(ROOT / 'tools/publish-release'))
    monkeypatch.setattr(launcher['runpy'], 'run_path', lambda *a, **kw: pytest.fail('implementation loaded'))
    with pytest.raises(SystemExit) as error:
        launcher['main'](args)
    assert error.value.code == 2


def test_symlink_release_path_is_rejected(tmp_path, monkeypatch):
    launcher = runpy.run_path(str(ROOT / 'tools/publish-release'))
    path = Path('/tmp/onpc-release-test/source')
    original = Path.lstat
    link = tmp_path / 'link'
    link.symlink_to(tmp_path, target_is_directory=True)
    monkeypatch.setattr(Path, 'lstat', lambda self: original(link) if self == path else original(tmp_path))
    with pytest.raises(launcher['argparse'].ArgumentTypeError, match='symlinks'):
        launcher['release_path'](str(path))


def test_launcher_is_executable_and_help_does_not_access_network():
    result = subprocess.run([str(ROOT / 'tools/publish-release'), '--help'],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert 'prepare' in result.stdout and 'inspect' in result.stdout


@pytest.mark.parametrize('mode,gid_delta,accepted', [(0o40775, 0, True),
                                                   (0o40777, 0, False),
                                                   (0o40775, 1, False)])
def test_normal_release_umask_is_supported_but_other_writers_are_refused(monkeypatch, mode, gid_delta, accepted):
    from types import SimpleNamespace
    launcher = runpy.run_path(str(ROOT / 'tools/publish-release'))
    info = SimpleNamespace(st_mode=mode, st_uid=launcher['os'].getuid(),
                           st_gid=launcher['os'].getgid() + gid_delta)
    monkeypatch.setattr(Path, 'lstat', lambda self: info)
    value = '/tmp/onpc-release-test/source'
    if accepted:
        assert launcher['release_path'](value) == Path(value)
    else:
        with pytest.raises(launcher['argparse'].ArgumentTypeError):
            launcher['release_path'](value)
