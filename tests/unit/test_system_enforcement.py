"""Trust-fixture writes refuse substituted paths before changing policy."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_enforcement as enforcement


@pytest.mark.parametrize('fault', ['file', 'symlink', 'unsafe-parent'])
def test_future_trust_refuses_foreign_file_or_parent_before_mutation(monkeypatch, tmp_path, fault):
    target = tmp_path / 'Versioned-2.AppImage'
    target.write_bytes(b'future fixture')
    trust = tmp_path / 'trust.d/future.trust'
    trust.parent.mkdir()
    monkeypatch.setattr(enforcement, 'FUTURE_TRUST', trust)
    monkeypatch.setattr(enforcement, 'native_paths', lambda variant: (target, None, None))
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement.guest, 'sha', lambda path: 'a' * 64)
    native_lstat = type(trust).lstat
    monkeypatch.setattr(type(trust), 'lstat', lambda path: (
        SimpleNamespace(st_mode=0o40777 if fault == 'unsafe-parent' else 0o40755, st_uid=0)
        if path in trust.parents else native_lstat(path)))
    if fault == 'file':
        trust.write_text('foreign')
    elif fault == 'symlink':
        trust.symlink_to(tmp_path / 'missing')
    run = Mock()
    monkeypatch.setattr(enforcement.guest, 'run', run)
    with pytest.raises(enforcement.guest.GuestError, match=(
            'unsafe-trust-parent' if fault == 'unsafe-parent' else 'future-trust-collision')):
        enforcement.trust_future()
    run.assert_not_called()
