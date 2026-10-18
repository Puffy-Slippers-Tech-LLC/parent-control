"""PAM history guards with private files and command doubles; no native actions."""

import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace
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
    monkeypatch.setattr(variants, 'COMPLETE', tmp_path / 'complete')
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


def prepare_doubles(private, monkeypatch):
    import guest_test_dependencies
    monkeypatch.setattr(guest_test_dependencies, 'verify_pam_compatibility', Mock())
    monkeypatch.setattr(variants, 'effective_stack', Mock())
    monkeypatch.setattr(variants.guest, 'pam_service_state', lambda: {'native': 'captured'})
    (private / 'pam/gdm-password').write_bytes(b'session required pam_unix.so\n')


def test_local_override_restores_exact_bytes_metadata_without_vendor_write(private, monkeypatch):
    prepare_doubles(private, monkeypatch)
    source = private / 'vendor/systemd-user'
    source.write_bytes(b'# native distro source\nsession required pam_systemd.so\n')
    before = variants.identity(source)
    saved = variants.prepare('administrator-override', Mock())
    target = private / 'pam/systemd-user'
    assert target.read_bytes() == before[-1] + variants.COMMENT
    assert variants.identity(source) == before
    # Model package publication and exact original restoration as new inodes.
    replacement = private / 'pam/restored'
    replacement.write_bytes(bytes.fromhex(saved['override_bytes']))
    replacement.chmod(0o644)
    replacement.replace(target)
    record = Mock()
    variants.verify_override(saved, record)
    record.assert_called_once()
    target.write_bytes(target.read_bytes() + b'# foreign edit\n')
    with pytest.raises(variants.guest.GuestError, match='override-not-restored-exactly'):
        variants.verify_override(saved, Mock())
    assert variants.identity(source) == before


def test_local_override_refuses_existing_local_file(private, monkeypatch):
    prepare_doubles(private, monkeypatch)
    source = private / 'vendor/systemd-user'
    source.write_bytes(b'session required pam_systemd.so\n')
    target = private / 'pam/systemd-user'
    target.write_bytes(b'# existing administrator policy\n')
    with pytest.raises(variants.guest.GuestError, match='mutation-collision'):
        variants.prepare('administrator-override', Mock())
    assert target.read_bytes() == b'# existing administrator policy\n'
    assert source.read_bytes() == b'session required pam_systemd.so\n'


@pytest.mark.parametrize('drop_mandatory', [False, True])
def test_plain_profile_allows_only_optional_rule_removal(private, monkeypatch, drop_mandatory):
    prepare_doubles(private, monkeypatch)
    profile = private / 'lxc-cgroups'
    profile.write_bytes(b'Session:\n optional pam_cgfs.so -c freezer,memory,name=systemd\n')
    monkeypatch.setattr(variants, 'optional_profile', lambda: 'actual-native-profile')
    mandatory = b'session required pam_unix.so\n'
    optional = b'session optional pam_cgfs.so -c freezer,memory,name=systemd\n'
    for name in variants.STACKS:
        (private / 'pam' / name).write_bytes(mandatory + optional)

    def disable(argv):
        assert argv == ['pam-auth-update', '--package', '--disable', 'actual-native-profile']
        for name in variants.STACKS:
            (private / 'pam' / name).write_bytes(b'' if drop_mandatory else mandatory)

    monkeypatch.setattr(variants.guest, 'run', disable)
    if drop_mandatory:
        with pytest.raises(variants.guest.GuestError, match='changed-other-security-rules'):
            variants.prepare('plain', Mock())
    else:
        saved = variants.prepare('plain', Mock())
        assert all(rows == [['session', 'required', 'pam_unix.so'], variants.CGFS]
                   for rows in saved['plain_original'].values())
        assert all((private / 'pam' / name).read_bytes() == mandatory for name in variants.STACKS)


@pytest.mark.parametrize('layout', ['continued', 'inline', 'absent', 'ambiguous', 'wrong-options'])
def test_optional_profile_uses_native_package_files_and_exact_reviewed_rule(monkeypatch, layout):
    directory = Path('/usr/share/pam-configs')
    native = directory / 'cgfs'
    rule = ' '.join(variants.CGFS[1:]).encode()
    content = b'Session:' + (b'\n ' if layout == 'continued' else b' ') + rule + b'\n'
    if layout == 'wrong-options':
        content = content.replace(b'freezer,memory,name=systemd', b'unreviewed')
    files = {native: content} if layout != 'absent' else {}
    if layout == 'ambiguous':
        files[directory / 'second-profile'] = content
    run = Mock(return_value='\n'.join(['/usr/lib/security/pam_cgfs.so', *map(str, files)]))
    monkeypatch.setattr(variants.guest, 'run', run)
    inspected = Mock(side_effect=lambda path: (files[path],))
    monkeypatch.setattr(variants, 'identity', inspected)
    if layout in ('continued', 'inline'):
        assert variants.optional_profile() == 'cgfs'
    else:
        with pytest.raises(variants.guest.GuestError, match='reviewed-cgfs-profile'):
            variants.optional_profile()
    run.assert_called_once_with(['dpkg-query', '-L', 'libpam-cgfs'])
    assert all(call.args[0].parent == directory for call in inspected.call_args_list)


@pytest.mark.parametrize('stream', ['stdout', 'stderr', 'absent'])
def test_configuration_receipt_uses_exact_transaction_output_not_volatile_notice_file(
        private, monkeypatch, stream):
    commands = SimpleNamespace(directory=private / 'diagnostics', sequence=7)
    monkeypatch.setattr(variants.guest, 'commands', commands)
    output = commands.directory / 'command-0007.txt'
    output.write_bytes(variants.CONFIGURED if stream == 'stdout' else b'transaction output')
    output.chmod(0o600)
    if stream == 'stderr':
        error = commands.directory / 'command-0007-stderr.txt'
        error.write_bytes(b'>>> ' + variants.CONFIGURED + b'\n')
        error.chmod(0o600)
    assert (variants.CONFIGURED in variants.configuration_output()) == (stream != 'absent')
    assert not variants.COMPLETE.exists()


@pytest.mark.parametrize('fault', ['none', 'unsupported-feature', 'lost-mandatory'])
def test_fedora_sssd_input_uses_native_selection_and_preserves_required_modules(
        private, monkeypatch, fault):
    prepare_doubles(private, monkeypatch)
    monkeypatch.setattr(variants, 'fedora', lambda: True)
    names = ('system-auth', 'password-auth')
    before = b'account required pam_unix.so\nsession required pam_limits.so\n'
    for name in names:
        (private / 'pam' / name).write_bytes(before)
    selection = ['local with-fingerprint']
    calls = []

    def run(argv):
        calls.append(argv)
        if argv == ['authselect', 'check']:
            return 'Current configuration is valid.'
        if argv == ['authselect', 'current', '--raw']:
            return selection[0]
        if argv == ['authselect', 'list-features', 'sssd']:
            return '' if fault == 'unsupported-feature' else 'with-fingerprint'
        assert argv == ['authselect', 'select', 'sssd', 'with-fingerprint']
        selection[0] = 'sssd with-fingerprint'
        for name in names:
            (private / 'pam' / name).write_bytes(
                (b'' if fault == 'lost-mandatory' else before) + b'session optional pam_sss.so\n')
        return ''

    monkeypatch.setattr(variants.guest, 'run', run)
    if fault == 'none':
        state = variants.prepare('distro-profile', Mock())
        assert state['authselect_baseline'] == 'local with-fingerprint'
        assert state['authselect_original'] == 'sssd with-fingerprint'
        assert state['authselect_baseline_stacks'] == {
            name: [['account', 'required', 'pam_unix.so'], ['session', 'required', 'pam_limits.so']]
            for name in names}
    else:
        with pytest.raises(variants.guest.GuestError, match='(unsupported-sssd|removed-mandatory)'):
            variants.prepare('distro-profile', Mock())
    assert all('--force' not in argv for argv in calls)
    if fault == 'unsupported-feature':
        assert not any(argv[1] == 'select' for argv in calls)
        assert all((private / 'pam' / name).read_bytes() == before for name in names)


@pytest.mark.parametrize('failure', ['none', 'missing-reason', 'broker-started', 'policy-changed',
                                     'candidate-edited'])
def test_pending_vendor_requires_specific_refusal_preservation_then_normal_retry(
        private, monkeypatch, failure):
    for name in ('gdm-password', 'systemd-user'):
        (private / 'pam' / name).write_bytes(b'owned installed PAM\n')
    (private / 'state/kiosk-confinement.json').write_text('{"owned": true}')
    for name in ('migration-in-progress', 'package-activation-pending'):
        (private / 'state' / name).write_bytes(b'')
    (private / 'state/kiosk-configuration-account.json').write_text(
        json.dumps({'uid': 1234, 'phase': 'quarantined'}))
    diagnostic = private / 'diagnostics/command-0001.txt'
    state = {'gdm_original': b'original distro stack\n'.hex(),
             'policy': {'child': 'original-policy'}, 'accounts': {'child': 1001}}
    commands = SimpleNamespace(directory=diagnostic.parent, sequence=1, last_returncode=1,
                               run=Mock(return_value=b''))
    monkeypatch.setattr(variants.guest, 'commands', commands)
    monkeypatch.setattr(variants.guest, 'verify_package_payload', Mock())
    monkeypatch.setattr(variants, 'ordinary_controls', Mock())
    monkeypatch.setattr(variants.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1234))
    monkeypatch.setattr(variants.runpy, 'run_path', lambda _: {'kiosk_account_expiry': lambda _: 1})
    monkeypatch.setattr(variants, 'policy_state', lambda _: {
        'child': 'changed-policy' if failure == 'policy-changed' else 'original-policy'})

    def install():
        diagnostic.write_bytes(b'unrelated failure' if failure == 'missing-reason' else
                               b'kiosk confinement failed reason=pending-distribution-pam-update\n')
        diagnostic.chmod(0o600)
        if failure == 'candidate-edited':
            (private / 'pam/gdm-password.dpkg-dist').write_bytes(b'foreign pending edit')
        raise variants.guest.CommandError('native-package-failed')

    def run(argv):
        if '--property=ActiveState' in argv:
            return 'active' if failure == 'broker-started' else 'inactive'
        if '--property=ConditionResult' in argv:
            return 'no'
        if '--property=MainPID' in argv:
            return '0'
        raise AssertionError(argv)

    monkeypatch.setattr(variants.guest, 'install_package', install)
    monkeypatch.setattr(variants.guest, 'run', run)
    retry = Mock()
    monkeypatch.setattr(variants, 'retry_configuration', retry)
    before = {name: (private / 'pam' / name).read_bytes()
              for name in ('gdm-password', 'systemd-user')}
    record = Mock()
    if failure == 'none':
        variants.pending_retry(state, record)
        retry.assert_called_once_with()
        assert any(key == 'onpc.pam-variants.conflict.refused' for key, _ in
                   (call.args for call in record.call_args_list))
    else:
        with pytest.raises(variants.guest.GuestError):
            variants.pending_retry(state, record)
        retry.assert_not_called()
    assert state['policy'] == {'child': 'original-policy'}
    assert before == {name: (private / 'pam' / name).read_bytes() for name in before}
    candidate = private / 'pam/gdm-password.dpkg-dist'
    if failure == 'candidate-edited':
        assert candidate.read_bytes() == b'foreign pending edit'
    else:
        assert not candidate.exists()


@pytest.mark.parametrize('entry,boot_field', [
    ('verify_reboot', 'boot'), ('remove', 'configured_boot'),
    ('verify_removed_reboot', 'removal_boot')])
def test_each_reboot_boundary_refuses_same_boot_before_product_actions(monkeypatch, entry, boot_field):
    monkeypatch.setattr(variants.guest, 'guard', Mock())
    monkeypatch.setattr(variants, 'load', lambda _: {boot_field: 'same-boot'})
    monkeypatch.setattr(variants, 'boot', lambda: 'same-boot')
    installed, removed, execute = Mock(), Mock(), Mock()
    monkeypatch.setattr(variants.guest, 'installed', installed)
    monkeypatch.setattr(variants.removal, 'verify_removed', removed)
    monkeypatch.setattr(variants, 'verify_execution_boundary', execute)
    with pytest.raises(variants.guest.GuestError, match='reboot-not-observed'):
        getattr(variants, entry)(Mock(), 'plain')
    installed.assert_not_called()
    removed.assert_not_called()
    execute.assert_not_called()


@pytest.mark.parametrize('change', ['policy', 'preferences', 'none'])
def test_policy_comparison_uses_independent_live_state_before_acceptance(monkeypatch, change):
    state = {'accounts': {'child': 1001}, 'policy': {'child': 'captured'}, 'preferences': 'saved'}
    monkeypatch.setattr(variants, 'policy_state', lambda _: {
        'child': 'changed' if change == 'policy' else 'captured'})
    monkeypatch.setattr(variants.removal, 'preference_digest', lambda _:
                        'changed' if change == 'preferences' else 'saved')
    record = Mock()
    if change == 'none':
        variants.verify_policy(state, record, 'configured')
        record.assert_called_once()
    else:
        with pytest.raises(variants.guest.GuestError, match='saved-(policy|preferences)-changed'):
            variants.verify_policy(state, record, 'configured')
        record.assert_not_called()
