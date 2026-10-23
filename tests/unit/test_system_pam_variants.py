"""PAM fixture edits preserve collisions and refuse changed restoration targets."""

import os
import stat
from unittest.mock import Mock

import pytest

import system_pam_variants as variants
import system_kiosk_accounts as accounts
import system_removal_faults as faults


@pytest.fixture(autouse=True)
def native_creation_mask():
    """Model the native root file-creation mask, restoring this worker afterward."""
    previous = os.umask(0o022)
    try:
        yield
    finally:
        os.umask(previous)


@pytest.fixture
def private(tmp_path, monkeypatch):
    """Keep real inode/byte checks, substituting only guest-root ownership."""
    def parents(path):
        assert path.is_relative_to(tmp_path)
        for parent in path.parents:
            if parent == tmp_path.parent:
                break
            assert parent.is_dir() and not parent.is_symlink()
            assert parent.stat().st_uid == os.getuid()
            assert not parent.stat().st_mode & 0o022

    def read(path, *, optional=False, private=False):
        parents(path)
        if optional and not os.path.lexists(path):
            return None
        info = path.lstat()
        assert stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
        assert info.st_nlink == 1 and not info.st_mode & 0o022
        assert not private or stat.S_IMODE(info.st_mode) == 0o600
        return path.read_bytes()

    monkeypatch.setattr(faults, 'OWNER_UID', os.getuid())
    monkeypatch.setattr(faults, 'parents', parents)
    monkeypatch.setattr(variants, 'parents', parents)
    monkeypatch.setattr(accounts, 'owned_bytes', read)
    monkeypatch.setattr(variants, 'owned_bytes', read)
    monkeypatch.setattr(variants, 'fedora', lambda: False)
    monkeypatch.setattr(variants.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(variants, 'boot', lambda: 'initial-boot')
    for name in ('pam', 'vendor', 'state', 'diagnostics'):
        (tmp_path / name).mkdir(mode=0o700)
    monkeypatch.setattr(variants, 'PAM', tmp_path / 'pam')
    monkeypatch.setattr(variants, 'VENDOR', tmp_path / 'vendor')
    monkeypatch.setattr(variants, 'STATE', tmp_path / 'state')
    return tmp_path


@pytest.mark.parametrize('collision', ['regular', 'dangling-link'])
def test_creation_preserves_foreign_collision(private, collision):
    target = private / 'pam/candidate'
    if collision == 'regular':
        target.write_bytes(b'foreign bytes')
    else:
        target.symlink_to(private / 'missing')
    before = target.lstat()
    with pytest.raises(variants.guest.GuestError, match='mutation-collision'):
        variants.create_owned(target, b'owned bytes')
    assert target.lstat().st_ino == before.st_ino
    if collision == 'regular':
        assert target.read_bytes() == b'foreign bytes'
    else:
        assert target.is_symlink() and not target.exists()


@pytest.mark.parametrize('change', ['bytes', 'mode', 'inode', 'none'])
def test_owned_resolution_rejects_changed_bytes_metadata_and_inode(private, change):
    target = private / 'pam/candidate'
    expected = variants.create_owned(target, b'owned bytes')
    inode = variants.identity(target)[:2]
    if change == 'bytes':
        target.write_bytes(b'foreign edit')
    elif change == 'mode':
        target.chmod(0o600)
    elif change == 'inode':
        replacement = private / 'pam/replacement'
        replacement.write_bytes(b'owned bytes')
        replacement.chmod(0o644)
        replacement.replace(target)
    if change == 'none':
        variants.unlink_owned(target, expected, inode=inode)
        assert not target.exists()
    else:
        with pytest.raises(variants.guest.GuestError, match='mutation-(identity|inode)-changed'):
            variants.unlink_owned(target, expected, inode=inode)
        assert target.exists()


@pytest.mark.parametrize('failure', ['none', 'probe-failed', 'bytes', 'mode', 'inode', 'xattrs'])
def test_administrator_auth_and_account_authority_with_identity_safe_restoration(
        private, monkeypatch, failure):
    target = private / 'pam/gdm-password'
    original = b'auth include native-auth\naccount include native-account\n'
    target.write_bytes(original)
    initial = variants.identity(target)
    controls = Mock()
    monkeypatch.setattr(variants, 'ordinary_controls', controls)
    writes = []

    def write(path, info, expected, contents):
        # Retain real bytes/inodes under tmp_path; shared editor's root-owner
        # enforcement has its own tests. Check its exact scenario operands here.
        assert path == target
        assert (info.st_dev, info.st_ino) == initial[:2]
        assert variants.identity(path)[:2] == initial[:2]
        assert path.read_bytes() == expected
        writes.append((expected, contents))
        path.write_bytes(contents)

    monkeypatch.setattr(variants.removal, 'write_hook', write)

    def probe(expected_account, stage, record, *, expected_authenticate=0):
        if stage.endswith('administrator-auth'):
            assert expected_account is None and expected_authenticate == variants.PAM_AUTH_ERR
            assert target.read_bytes().startswith(
                b'auth [success=1 default=ignore] pam_succeed_if.so quiet user != oh-no-parent-control\n'
                b'auth requisite pam_deny.so\n')
            if failure == 'probe-failed':
                raise variants.guest.GuestError('native-probe-failed')
            if failure == 'bytes':
                target.write_bytes(b'foreign administrator edit')
            elif failure == 'mode':
                target.chmod(0o600)
            elif failure == 'inode':
                replacement = target.with_name('replacement')
                replacement.write_bytes(target.read_bytes())
                replacement.chmod(0o644)
                replacement.replace(target)
            elif failure == 'xattrs':
                os.setxattr(target, 'user.onpc-test', b'foreign')
        elif stage.endswith('administrator-account'):
            assert expected_account == 7 and expected_authenticate == 0
            assert target.read_bytes().startswith(
                b'account [success=1 default=ignore] pam_succeed_if.so quiet user != oh-no-parent-control\n'
                b'account requisite pam_deny.so\n')
        else:
            assert expected_account == expected_authenticate == 0
            assert variants.identity(target) == initial

    native = Mock(side_effect=probe)
    monkeypatch.setattr(variants, 'empty_authentication_probe', native)
    if failure == 'none':
        variants.verify_administrator_denials(Mock())
        assert len(writes) == 4 and native.call_count == 5
        assert controls.call_count == 4
        assert variants.identity(target) == initial
    elif failure == 'probe-failed':
        with pytest.raises(variants.guest.GuestError, match='native-probe-failed'):
            variants.verify_administrator_denials(Mock())
        assert len(writes) == 2 and variants.identity(target) == initial
    else:
        with pytest.raises(variants.guest.GuestError, match='administrator-policy-identity-changed'):
            variants.verify_administrator_denials(Mock())
        assert len(writes) == 1
        assert variants.identity(target) != initial
