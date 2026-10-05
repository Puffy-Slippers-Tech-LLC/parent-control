"""Private native-policy provenance and lifecycle files with RPM/DNF doubles."""
import grp
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from types import SimpleNamespace

import pytest

from tests.support.paths import ROOT


@pytest.fixture
def policy_machine(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('onpc_fedora_execution_policy',
                                                ROOT / 'packaging/fedora_execution_policy.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'OWNER', os.getuid())
    policy = module.Policy(tmp_path)
    settings = dict(installed=True, active=False, enabled=False, reason='Dependency', unchanged=True,
                    service_error=False)
    commands, manifest = [], []
    group = grp.getgrgid(os.getgid()).gr_name

    def write(name, value, mode=0o644):
        path = policy.path(name)
        created = [parent for parent in path.parents if parent.is_relative_to(tmp_path) and not parent.exists()]
        path.parent.mkdir(parents=True, exist_ok=True)
        for parent in created:
            parent.chmod(0o755)
        path.write_text(value)
        path.chmod(mode)
        return path

    def stock():
        manifest.clear()
        files = {
            '/etc/fapolicyd/fapolicyd.conf': 'trust = rpmdb,file\n',
            '/etc/fapolicyd/fapolicyd-filter.conf': '# stock filter\n',
            '/etc/fapolicyd/fapolicyd.trust': '',
            '/usr/share/fapolicyd/default-ruleset.known-libs': '42-trusted-elf.rules\n90-deny-execute.rules\n',
            '/usr/share/fapolicyd/sample-rules/42-trusted-elf.rules': 'allow perm=execute all : trust=1\n',
            '/usr/share/fapolicyd/sample-rules/90-deny-execute.rules': 'deny_audit perm=execute all : all\n',
        }
        for name, value in files.items():
            path = write(name, value)
            manifest.append(f'{name}\t{hashlib.sha256(path.read_bytes()).hexdigest()}\t{path.stat().st_mode}\troot\t{group}\t0\n')
        for name in ('/etc/fapolicyd', '/etc/fapolicyd/rules.d', '/etc/fapolicyd/trust.d'):
            path = policy.path(name)
            path.mkdir(exist_ok=True)
            path.chmod(0o750)
            manifest.append(f'{name}\t\t{path.stat().st_mode}\troot\t{group}\t0\n')
        for name in ('42-trusted-elf.rules', '90-deny-execute.rules'):
            write('/etc/fapolicyd/rules.d/' + name,
                  policy.path('/usr/share/fapolicyd/sample-rules/' + name).read_text())
        write('/etc/fapolicyd/compiled.rules', 'stock compiled rules\n')
        # Real Fedora rules are ghost entries: these have no usable digest.
        manifest.append(f'/etc/fapolicyd/rules.d/*\t\t{stat.S_IFREG | 0o644}\troot\t{group}\t64\n')
        manifest.append(f'/etc/fapolicyd/compiled.rules\t\t{stat.S_IFREG | 0o644}\troot\t{group}\t64\n')

    def run(arguments):
        commands.append(arguments)
        if arguments[:2] == ['systemctl', 'show']:
            return SimpleNamespace(returncode=1 if settings['service_error'] else 0,
                                   stdout='LoadState=' + ('loaded' if settings['installed'] else 'not-found') +
                                   '\nActiveState=' + ('active' if settings['active'] else 'inactive') +
                                   '\nUnitFileState=' + ('enabled' if settings['enabled'] else
                                                         'disabled' if settings['installed'] else '') + '\n')
        if arguments[0] == 'dnf5':
            assert '--installed' in arguments and '--cacheonly' in arguments and '--disable-repo=*' in arguments
            return SimpleNamespace(returncode=0, stdout='fapolicyd|' + settings['reason'])
        if arguments[0] == 'rpm':
            assert arguments[-1] == 'fapolicyd'
            query = arguments[3]
            if query == '%{NAME}':
                return SimpleNamespace(returncode=0 if settings['installed'] else 1,
                                       stdout='fapolicyd' if settings['installed'] else '')
            if query == '%{FILEDIGESTALGO}':
                return SimpleNamespace(returncode=0, stdout='8')
            return SimpleNamespace(returncode=0, stdout=''.join(manifest))
        assert arguments == ['/usr/sbin/fagenrules', '--check']
        return SimpleNamespace(returncode=0, stdout='/usr/sbin/fagenrules: ' +
                               ('No change' if settings['unchanged'] else 'Rules have changed and should be updated') + '\n')

    monkeypatch.setattr(policy, 'run', run)
    (tmp_path / 'var/lib').mkdir(parents=True)
    for path in tmp_path.rglob('*'):
        if path.is_dir():
            path.chmod(0o755)
    stock()
    return SimpleNamespace(module=module, policy=policy, settings=settings, commands=commands,
                           write=write, stock=stock, manifest=manifest, root=tmp_path)


def test_new_dependency_remove_purge_reinstall_uses_committed_reason_without_residue(policy_machine):
    machine = policy_machine
    policy = machine.policy
    shutil.rmtree(policy.path('/etc/fapolicyd'))
    machine.settings['installed'] = False
    policy.capture()
    assert policy.record()['basis'] == 'absent' and not policy.record()['permissive']
    machine.settings['installed'] = True
    machine.stock()
    assert policy.eligible()
    payload = (ROOT / 'data/fapolicyd/99-oh-no-parent-control-allow.rules').read_text()
    integration = '/etc/fapolicyd/rules.d/02-oh-no-parent-control-original-allow.rules'
    machine.write(integration, payload)
    machine.write('/var/lib/oh-no-parent-control/installed-fapolicyd-original-policy', payload, 0o600)
    policy.commit()
    assert policy.record()['permissive']
    policy.path(integration).unlink()
    (policy.state.parent / 'installed-fapolicyd-original-policy').unlink()
    assert policy.restore_stock()
    policy.cleanup()
    policy.state.parent.rmdir()  # Purge does not retain a provenance receipt.
    policy.capture()
    assert policy.record()['basis'] == 'dependency' and not policy.record()['permissive']
    assert any(command[0] == 'dnf5' for command in machine.commands)
    assert policy.eligible()


@pytest.mark.parametrize('reason', ['Dependency', 'Weak Dependency', 'User', 'Group', 'External User', 'None', ''])
@pytest.mark.parametrize('active,enabled', [(False, False), (True, False), (False, True)])
def test_only_unenforced_default_dependency_is_adopted(policy_machine, reason, active, enabled):
    machine = policy_machine
    machine.settings.update(reason=reason, active=active, enabled=enabled)
    machine.policy.capture()
    expected = not active and not enabled and reason in ('Dependency', 'Weak Dependency')
    assert (machine.policy.record()['basis'] == 'dependency') == expected
    assert machine.policy.record()['active'] is active
    assert machine.policy.record()['enabled'] is enabled
    assert machine.policy.eligible() is expected


@pytest.mark.parametrize('fault', ['changed-live-rule', 'custom-rule', 'trust-record', 'changed-config',
                                 'changed-sample', 'changed-list', 'symlink', 'hardlink', 'writable',
                'compiled-changed', 'old-rules', 'changed-directory-mode'])
def test_unknown_or_modified_native_policy_is_preserved(policy_machine, fault):
    machine = policy_machine
    target = machine.policy.path('/etc/fapolicyd/rules.d/90-deny-execute.rules')
    if fault == 'changed-live-rule':
        target.write_text('administrator policy\n')
    elif fault == 'custom-rule':
        machine.write('/etc/fapolicyd/rules.d/10-administrator.rules', 'deny perm=any all : all\n')
    elif fault == 'trust-record':
        machine.write('/etc/fapolicyd/trust.d/administrator.trust', 'administrator trust\n')
    elif fault == 'changed-config':
        machine.policy.path('/etc/fapolicyd/fapolicyd.conf').write_text('permissive = 1\n')
    elif fault == 'changed-sample':
        machine.policy.path('/usr/share/fapolicyd/sample-rules/90-deny-execute.rules').write_text('allow perm=any all : all\n')
    elif fault == 'changed-list':
        machine.policy.path('/usr/share/fapolicyd/default-ruleset.known-libs').write_text('90-deny-execute.rules\n')
    elif fault == 'symlink':
        target.unlink()
        target.symlink_to(machine.policy.path('/usr/share/fapolicyd/sample-rules/90-deny-execute.rules'))
    elif fault == 'hardlink':
        os.link(target, machine.root / 'linked-rule')
    elif fault == 'writable':
        target.chmod(0o664)
    elif fault == 'compiled-changed':
        machine.settings['unchanged'] = False
    elif fault == 'changed-directory-mode':
        machine.policy.path('/etc/fapolicyd').chmod(0o755)
    else:
        machine.write('/etc/fapolicyd/fapolicyd.rules', 'legacy administrator policy\n')
    machine.policy.capture()
    assert machine.policy.record()['basis'] == 'preserve'
    assert not machine.policy.eligible()
    assert not machine.policy.restore_stock()


def test_upgrade_and_configuration_retry_preserve_original_service_flags(policy_machine):
    machine = policy_machine
    machine.policy.capture()
    original = machine.policy.record()
    machine.write('/var/lib/oh-no-parent-control/fapolicyd-before-install/complete', '')
    machine.settings.update(active=True, enabled=True, reason='User')
    machine.commands.clear()
    machine.policy.capture()
    assert machine.policy.record() == original and not machine.commands
    pending = '/var/lib/oh-no-parent-control/fapolicyd-before-install.pending'
    machine.write(pending + '/active', '')
    machine.write(pending + '/enabled', '')
    machine.policy.flags()
    assert not machine.policy.path(pending + '/active').exists()
    assert not machine.policy.path(pending + '/enabled').exists()


@pytest.mark.parametrize('installed', [False, True])
def test_service_query_failure_never_authorizes_original_allow(policy_machine, installed):
    machine = policy_machine
    machine.settings.update(installed=installed, service_error=True)
    if not installed:
        shutil.rmtree(machine.policy.path('/etc/fapolicyd'))
    machine.policy.capture()
    assert machine.policy.record()['basis'] == 'preserve'
    assert not machine.policy.eligible()


@pytest.mark.parametrize('fault', ['symlink', 'hardlink', 'writable', 'foreign-purpose', 'extra-field', 'oversized'])
def test_pretrans_refuses_unowned_or_substituted_provenance(policy_machine, fault):
    machine = policy_machine
    machine.policy.capture()
    if fault == 'symlink':
        data = machine.policy.state.read_text()
        machine.policy.state.unlink()
        machine.policy.state.symlink_to(machine.write('/var/lib/foreign.json', data, 0o600))
    elif fault == 'hardlink':
        os.link(machine.policy.state, machine.root / 'linked-state')
    elif fault == 'writable':
        machine.policy.state.chmod(0o660)
    elif fault == 'oversized':
        machine.policy.state.write_text(' ' * 4097)
    else:
        value = machine.policy.record()
        value['purpose' if fault == 'foreign-purpose' else 'extra'] = 'foreign'
        machine.policy.state.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        machine.policy.capture()


def test_committed_original_allow_refuses_custom_configuration_on_retry(policy_machine):
    machine = policy_machine
    machine.policy.capture()
    payload = (ROOT / 'data/fapolicyd/99-oh-no-parent-control-allow.rules').read_text()
    machine.write('/etc/fapolicyd/rules.d/02-oh-no-parent-control-original-allow.rules', payload)
    machine.write('/var/lib/oh-no-parent-control/installed-fapolicyd-original-policy', payload, 0o600)
    machine.policy.commit()
    custom = machine.write('/etc/fapolicyd/rules.d/10-administrator.rules', 'administrator policy\n')
    with pytest.raises(ValueError, match='changed'):
        machine.policy.eligible()
    assert not machine.policy.restore_stock()
    assert custom.read_text() == 'administrator policy\n'


def test_embedded_pretrans_and_erased_payload_cleanup_share_standalone_source(tmp_path):
    import runpy
    renderer = runpy.run_path(str(ROOT / 'packaging/render_lifecycle.py'))
    renderer['rpm_scripts'](ROOT, tmp_path)
    source = (ROOT / 'packaging/fedora_execution_policy.py').read_text()
    for name in ('rpm-pretrans', 'rpm-pre', 'rpm-postun'):
        script = tmp_path / name
        assert source in script.read_text()
        result = subprocess.run(['/bin/sh', '-n', str(script)], capture_output=True, timeout=10)
        assert result.returncode == 0, result.stderr
    assert '%pretrans -f rpm-lifecycle/rpm-pretrans' in (ROOT / 'rpm/oh-no-parent-control.spec.in').read_text()
