"""Read-only bounded exports of historical native-history evidence."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

@pytest.mark.parametrize('fault', [None, 'mode', 'link', 'size', 'owner'])
@pytest.mark.parametrize('name', ['native-update-old.json', 'retained-ambient-observed-initial.json',
                                  'required-history-native-complete.json',
                                  'retained-manager-' + 'a' * 32 + '-intent.json'])
def test_native_collection_is_finite_private_bounded_and_redacted(tmp_path, monkeypatch, fault, name):
    import system_guest as guest
    monkeypatch.setattr(guest, 'PAYLOAD', tmp_path)
    (tmp_path / 'private').mkdir()
    source = tmp_path / 'private' / name
    source.write_text(json.dumps({'binding': 'sensitive-value'}))
    (tmp_path / 'private/native-update-foreign.json').write_text('{}')
    output = tmp_path / 'results'
    output.mkdir()
    original = Path.lstat
    def metadata(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path != source:
            return info
        return SimpleNamespace(st_mode=0o100600 if fault != 'mode' else 0o100644,
            st_nlink=2 if fault == 'link' else 1, st_uid=1000 if fault == 'owner' else 0,
            st_gid=0, st_size=9 * 1024 * 1024 if fault == 'size' else info.st_size)
    monkeypatch.setattr(Path, 'lstat', metadata)
    redact = lambda value: value.replace('sensitive-value', '[redacted]')
    if fault:
        with pytest.raises(guest.GuestError, match='collection-checkpoint'):
            guest.collect_native_checkpoints(output, redact)
        assert not list(output.iterdir())
    else:
        guest.collect_native_checkpoints(output, redact)
        assert [path.name for path in output.iterdir()] == [source.name]
        assert json.loads((output / source.name).read_text()) == {'binding': '[redacted]'}
        assert 'sensitive-value' in source.read_text()


@pytest.mark.parametrize('command', ['native-establish-old', 'native-retired', 'native-loader-drained'])
def test_retired_native_worker_routes_refuse_before_guard_or_mutation(monkeypatch, capsys, command):
    import system_guest as guest

    guard = Mock(side_effect=AssertionError('retired worker reached guest operations'))
    monkeypatch.setattr(guest, 'guard', guard)
    assert guest.main([command]) == 1
    guard.assert_not_called()
    assert capsys.readouterr().err == 'onpc-system: outcome=failed category=invalid-command\n'
