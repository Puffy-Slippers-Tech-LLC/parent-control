"""Upgrade checkpoints preserve foreign files and exact attempt ownership."""

import os

import pytest

import system_previous_upgrade as upgrade


@pytest.fixture
def checkpoint(tmp_path, monkeypatch):
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    monkeypatch.setattr(upgrade.guest, 'PAYLOAD', tmp_path)
    # Unit fixtures belong to the unprivileged launcher; emulate root metadata.
    original_lstat = upgrade.Path.lstat
    original_fstat = upgrade.os.fstat

    def root_info(info):
        fields = list(info)
        fields[4] = fields[5] = 0
        return os.stat_result(fields)

    monkeypatch.setattr(upgrade.Path, 'lstat', lambda path: root_info(original_lstat(path)))
    monkeypatch.setattr(upgrade.os, 'fstat', lambda fd: root_info(original_fstat(fd)))
    marker = dict(run='a' * 32, package_sha256='b' * 64,
                  baseline_sha256='c' * 64, selected_inputs_sha256='d' * 64)
    return marker, {'schema': 1, 'binding': upgrade.binding(marker)}


def test_checkpoint_is_private_durable_and_bound_to_exact_attempt(checkpoint):
    marker, state = checkpoint
    upgrade.save_state(state)
    assert upgrade.load_state(marker) == state
    assert upgrade.state_path().stat().st_mode & 0o777 == 0o600
    marker['selected_inputs_sha256'] = 'e' * 64
    with pytest.raises(upgrade.guest.GuestError, match='checkpoint-attempt'):
        upgrade.load_state(marker)


def test_checkpoint_never_overwrites_or_follows_existing_file(checkpoint, tmp_path):
    marker, state = checkpoint
    target = tmp_path / 'foreign'
    target.write_text('foreign')
    upgrade.state_path().symlink_to(target)
    with pytest.raises(OSError):
        upgrade.save_state(state)
    with pytest.raises(OSError):
        upgrade.load_state(marker)
    assert target.read_text() == 'foreign'
