"""Preserve site policy and reject ambiguous edits before kernel activation."""

from tests.support.modules import load_module
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.support.paths import ROOT
policy = load_module('onpc_test_graphical_policy', ROOT / 'tools/install_graphical_test_policy.py')


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
def test_fedora_and_hosts_without_libvirt_need_no_apparmor_changes(tmp_path, monkeypatch, distribution):
    monkeypatch.setattr(policy.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(policy.sys, 'argv', ['install_graphical_test_policy.py'])
    monkeypatch.setattr(policy.platform, 'freedesktop_os_release', lambda: {'ID': distribution})
    monkeypatch.setattr(policy, 'PROFILE', tmp_path / 'absent-profile')
    monkeypatch.setattr(policy, 'QEMU_ABSTRACTION', tmp_path / 'absent-abstraction')
    if distribution == 'fedora':
        policy.PROFILE.write_text('existing profile must stay untouched')
        policy.QEMU_ABSTRACTION.write_text('existing abstraction must stay untouched')
    with patch.object(policy, 'install') as install, patch.object(policy, 'install_qemu_policy') as qemu:
        policy.main()
    install.assert_not_called()
    qemu.assert_not_called()


def test_managed_policy_preserves_site_rules_and_is_idempotent():
    site = '# unrelated site policy\n/specific/path r,\n'
    added = policy.updated_local(site, 'first-rule,')
    assert added.startswith(site)
    assert policy.updated_local(added, 'first-rule,') == added
    replaced = policy.updated_local(added + '# suffix\n', 'new-rule,')
    assert replaced.startswith(site) and replaced.endswith('# suffix\n')
    assert 'first-rule' not in replaced and replaced.count('new-rule') == 1


@pytest.mark.parametrize('libvirtd,qemu', [(True, False), (False, True), (True, True)])
def test_only_installed_apparmor_components_are_refreshed(tmp_path, monkeypatch, libvirtd, qemu):
    monkeypatch.setattr(policy.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(policy.sys, 'argv', ['install_graphical_test_policy.py'])
    monkeypatch.setattr(policy.platform, 'freedesktop_os_release', lambda: {'ID': 'ubuntu'})
    monkeypatch.setattr(policy, 'PROFILE', tmp_path / 'profile')
    monkeypatch.setattr(policy, 'QEMU_ABSTRACTION', tmp_path / 'abstraction')
    for path, present in ((policy.PROFILE, libvirtd), (policy.QEMU_ABSTRACTION, qemu)):
        if present:
            path.write_text('installed AppArmor component')
    with patch.object(policy, 'install') as install, patch.object(policy, 'install_qemu_policy') as install_qemu:
        policy.main()
    assert install.call_count == int(libvirtd)
    assert install_qemu.call_count == int(qemu)


@pytest.mark.parametrize('component', ['PROFILE', 'QEMU_ABSTRACTION'])
def test_substituted_apparmor_component_is_still_refused(tmp_path, monkeypatch, component):
    monkeypatch.setattr(policy.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(policy.sys, 'argv', ['install_graphical_test_policy.py'])
    monkeypatch.setattr(policy.platform, 'freedesktop_os_release', lambda: {'ID': 'ubuntu'})
    monkeypatch.setattr(policy, 'PROFILE', tmp_path / 'profile')
    monkeypatch.setattr(policy, 'QEMU_ABSTRACTION', tmp_path / 'abstraction')
    getattr(policy, component).symlink_to('missing-target')
    with pytest.raises(ValueError, match='unsafe-system-file'):
        policy.main()


@pytest.mark.parametrize('bad', [policy.BEGIN, policy.END, policy.BEGIN * 2 + policy.END,
                                policy.END + policy.BEGIN])
def test_ambiguous_block_is_refused(bad):
    with pytest.raises(ValueError):
        policy.updated_local(bad, 'rule,')


def test_compile_failure_leaves_system_file_untouched(tmp_path):
    local, profile = tmp_path / 'local', tmp_path / 'profile'
    local.write_text('# site rules\n')
    profile.write_text('profile libvirtd {\n' + policy.INCLUDE + '\n}\n')
    with patch.object(policy, 'LOCAL', local), patch.object(policy, 'PROFILE', profile), \
            patch.object(policy, 'trusted_file', side_effect=lambda p: p.read_text()), \
            patch.object(policy.subprocess, 'run', side_effect=RuntimeError('syntax failure')) as run:
        with pytest.raises(RuntimeError, match='syntax failure'):
            policy.install()
    assert local.read_text() == '# site rules\n'
    assert '--skip-kernel-load' in run.call_args.args[0]
    assert run.call_count == 1


def test_qemu_compile_failure_creates_no_dropin(tmp_path):
    target = tmp_path / 'libvirt-qemu.d/onpc-graphical-tests'
    with patch.object(policy, 'QEMU_DROPIN', target), \
            patch.object(policy, 'trusted_file', return_value=policy.QEMU_INCLUDE), \
            patch.object(policy.subprocess, 'run', side_effect=RuntimeError('syntax failure')) as run:
        with pytest.raises(RuntimeError, match='syntax failure'):
            policy.install_qemu_policy()
    assert not target.parent.exists()
    assert '--skip-kernel-load' in run.call_args.args[0]
    assert '--replace' not in run.call_args.args[0]


def test_missing_local_policy_is_created_once_and_repeat_preserves_it(tmp_path):
    local, profile = tmp_path / 'local', tmp_path / 'profile'
    profile.write_text('profile libvirtd {\n' + policy.INCLUDE + '\n}\n')
    with patch.object(policy, 'LOCAL', local), patch.object(policy, 'PROFILE', profile), \
            patch.object(policy, 'trusted_file', side_effect=lambda path: path.read_text()), \
            patch.object(policy.subprocess, 'run') as run:
        policy.install()
        installed = local.read_text()
        inode = local.stat().st_ino
        policy.install()
    assert local.read_text() == installed
    assert local.stat().st_ino == inode
    assert installed.count(policy.BEGIN) == 1
    assert run.call_count == 4  # Validate and reload, including a retry after load failure.


def test_qemu_rule_is_idempotent_without_reloading_guest_profiles(tmp_path):
    target = tmp_path / 'libvirt-qemu.d/onpc-graphical-tests'
    target.parent.mkdir(mode=0o755)
    site = '# preserved site rule\n'
    target.write_text(site)
    expected = policy.updated_local(site, (ROOT / 'config/apparmor/onpc-graphical-qemu-tests').read_text())

    def trusted(path):
        return policy.QEMU_INCLUDE if path == policy.QEMU_ABSTRACTION else path.read_text()

    real_lstat = Path.lstat

    def lstat(path):
        result = real_lstat(path)
        if path == target.parent:
            from types import SimpleNamespace
            return SimpleNamespace(st_mode=result.st_mode, st_uid=0)
        return result

    with patch.object(policy, 'QEMU_DROPIN', target), patch.object(policy, 'trusted_file', side_effect=trusted), \
            patch.object(Path, 'lstat', lstat), patch.object(policy.subprocess, 'run') as run:
        policy.install_qemu_policy()
        assert target.read_text() == expected
        policy.install_qemu_policy()
        assert target.read_text() == expected
    assert run.call_count == 2
    assert all('--skip-kernel-load' in call.args[0] and '--replace' not in call.args[0]
               for call in run.call_args_list)
