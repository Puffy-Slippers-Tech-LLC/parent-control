"""PAM history guards with private files and command doubles; no native actions."""

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


@pytest.mark.parametrize('fedora', [False, True])
@pytest.mark.parametrize('layout', ['local', 'vendor-only'])
@pytest.mark.parametrize('failure', ['none', 'missing-receipt', 'package-failed', 'policy-changed',
                                     'candidate-edited', 'candidate-replaced', 'service-edited',
                                     'service-replaced', 'vendor-edited', 'routing-changed',
                                     'record-edited', 'barrier-retained'])
def test_pending_vendor_configures_preserving_candidate_services_and_restoration(
        private, monkeypatch, fedora, layout, failure):
    monkeypatch.setattr(variants, 'fedora', lambda: fedora)
    (private / 'pam/gdm-password').write_bytes(b'owned installed PAM\n')
    local = private / 'pam/systemd-user'
    vendor = private / 'vendor/systemd-user'
    vendor.write_bytes(b'unchanged native vendor PAM\n')
    if layout == 'local':
        local.write_bytes(b'owned installed PAM\n')
    restoration = private / 'state' / ('fedora-authselect.json' if fedora else
                                      'malcontent-pam-before-install')
    restoration.write_bytes(b'{"phase":"installed","original":["sssd"]}' if fedora else b'enabled\n')
    restoration.chmod(0o600)
    candidate = private / 'pam' / ('gdm-password.rpmnew' if fedora else 'gdm-password.dpkg-dist')
    diagnostic = private / 'diagnostics/command-0001.txt'
    state = {'gdm_original': b'original distro stack\n'.hex(),
             'policy': {'child': 'original-policy'}, 'accounts': {'child': 1001}}
    commands = SimpleNamespace(directory=diagnostic.parent, sequence=1)
    monkeypatch.setattr(variants.guest, 'commands', commands)
    monkeypatch.setattr(variants.guest, 'reboot_requested', lambda: False)
    installed = Mock()
    monkeypatch.setattr(variants.guest, 'installed', installed)
    ready = Mock()
    monkeypatch.setattr(variants.removal, 'verify_loaded_confinement', ready)
    monkeypatch.setattr(variants, 'ordinary_controls', Mock())
    monkeypatch.setattr(variants, 'empty_authentication_probe', Mock())
    checked_policy = Mock(side_effect=variants.guest.GuestError('saved-policy-changed')
                          if failure == 'policy-changed' else None)
    monkeypatch.setattr(variants, 'verify_policy', checked_policy)
    monkeypatch.setattr(variants.guest, 'run', Mock())

    def replace(path):
        temporary = path.with_name('foreign-replacement')
        temporary.write_bytes(path.read_bytes())
        temporary.chmod(stat.S_IMODE(path.stat().st_mode))
        temporary.replace(path)

    def install():
        if install_mock.call_count == 2:
            assert not candidate.exists()
            return
        assert candidate.exists()
        assert candidate.read_bytes().startswith(bytes.fromhex(state['gdm_original']))
        diagnostic.write_bytes(b'unrelated output' if failure == 'missing-receipt' else
                               variants.CONFIGURED)
        diagnostic.chmod(0o600)
        if failure == 'candidate-edited':
            candidate.write_bytes(b'foreign pending edit')
        elif failure == 'candidate-replaced':
            replace(candidate)
        elif failure == 'service-edited':
            (private / 'pam/gdm-password').write_bytes(b'foreign service edit')
        elif failure == 'service-replaced':
            replace(private / 'pam/gdm-password')
        elif failure == 'vendor-edited':
            vendor.write_bytes(b'foreign vendor edit')
        elif failure == 'routing-changed':
            if layout == 'local':
                local.unlink()
            else:
                local.write_bytes(b'foreign local override')
        elif failure == 'record-edited':
            restoration.write_bytes(b'foreign restoration edit')
        elif failure == 'barrier-retained':
            (private / 'state/kiosk-configuration-account.json').write_bytes(b'{}')
        elif failure == 'package-failed':
            raise variants.guest.CommandError('native-package-failed')

    install_mock = Mock(side_effect=install)
    monkeypatch.setattr(variants.guest, 'install_package', install_mock)
    record = Mock()
    if failure == 'none':
        variants.pending_retry(state, record)
        assert install_mock.call_count == 2
        installed.assert_called_once_with(reboot_required=False)
        ready.assert_called_once_with()
        checked_policy.assert_called_once_with(state, record, 'pending-vendor')
        assert any(key == 'onpc.pam-variants.pending-vendor.preserved' for key, _ in
                   (call.args for call in record.call_args_list))
    else:
        with pytest.raises((variants.guest.GuestError, variants.guest.CommandError)):
            variants.pending_retry(state, record)
        assert install_mock.call_count == 1
    assert state['policy'] == {'child': 'original-policy'}
    if failure == 'candidate-edited':
        assert candidate.read_bytes() == b'foreign pending edit'
    elif failure == 'candidate-replaced':
        assert candidate.exists()
    else:
        assert not candidate.exists()
    if failure == 'routing-changed':
        if layout == 'local':
            assert not os.path.lexists(local)
        else:
            assert local.read_bytes() == b'foreign local override'
    elif layout == 'local':
        assert local.read_bytes() == b'owned installed PAM\n'
    else:
        assert not os.path.lexists(local)
    assert vendor.read_bytes() == (b'foreign vendor edit' if failure == 'vendor-edited' else
                                   b'unchanged native vendor PAM\n')
    if failure == 'service-edited':
        assert (private / 'pam/gdm-password').read_bytes() == b'foreign service edit'
    else:
        assert (private / 'pam/gdm-password').read_bytes() == b'owned installed PAM\n'
    if failure == 'record-edited':
        assert restoration.read_bytes() == b'foreign restoration edit'


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


@pytest.mark.parametrize('variant', variants.VARIANTS)
def test_first_reboot_retains_passwordless_use_policy_and_current_composition(monkeypatch, variant):
    state = {'boot': 'old-boot', 'ordinary': 'ordinary-snapshot'}
    monkeypatch.setattr(variants, 'load', lambda value: state if value == variant else None)
    monkeypatch.setattr(variants, 'boot', lambda: 'new-boot')
    for name in ('guard', 'installed'):
        monkeypatch.setattr(variants.guest, name, Mock())
    monkeypatch.setattr(variants.guest, 'reboot_cleared', lambda: True)
    monkeypatch.setattr(variants.guest, 'reboot_requested', lambda: False)
    monkeypatch.setattr(variants.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(variants, 'configuration_output', lambda: variants.CONFIGURED)
    doubles = {}
    for name in ('verify_ordinary', 'ordinary_controls', 'effective_stack',
                 'verify_session_composition', 'empty_authentication_probe',
                 'verify_administrator_denials', 'seed_policy', 'save',
                 'pending_retry', 'verify_policy', 'verify_visibility'):
        doubles[name] = Mock()
        monkeypatch.setattr(variants, name, doubles[name])
    install = Mock()
    monkeypatch.setattr(variants.guest, 'install_package', install)
    record = Mock()
    variants.verify_reboot(record, variant)
    doubles['verify_session_composition'].assert_called_once_with(record)
    doubles['empty_authentication_probe'].assert_called_once_with(
        0, 'pam-variant.first-reboot.empty-authentication', record)
    assert doubles['verify_administrator_denials'].call_count == (variant == 'administrator-override')
    assert doubles['pending_retry'].call_count == (variant == 'pending-vendor')
    assert install.call_count == (variant != 'pending-vendor')
    doubles['seed_policy'].assert_called_once_with(state)
    doubles['verify_policy'].assert_called_once_with(state, record, 'configured')
    assert state['configured_boot'] == 'new-boot'


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
    monkeypatch.setattr(variants, 'verify_session_composition', execute)
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
