"""Shared RPM source/payload contracts; no package install, VM or publication."""
import configparser
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tarfile

import pytest

from tests.support.paths import ROOT
from tests.support.package_scripts import machine, package_machine
from tests.support.shell import relocate_system_paths
from tools import build_rpm, package_inputs, rpm_builder


@pytest.fixture(scope='module')
def fedora_payload(tmp_path_factory):
    destination = tmp_path_factory.mktemp('fedora-payload')
    result = subprocess.run([
        'make', '--no-print-directory', '_install-product-files',
        f'DESTDIR={destination}', 'PACKAGE_DISTRIBUTION=fedora',
        'PAM_MODULE_DIR=/usr/lib64/security',
    ], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return destination


def test_fedora_payload_shares_runtime_and_has_native_integrations(fedora_payload):
    payload = fedora_payload
    assert not (payload / 'etc/apt').exists()
    assert not (payload / 'usr/share/pam-configs').exists()
    assert (payload / 'usr/lib64/security/pam_oh_no_parent_control.so').is_file()
    assert (payload / 'usr/libexec/oh-no-parent-control-fedora-pam').is_file()
    assert (payload / 'usr/lib/oh-no-parent-control/parent/oh_no_parent_control_parent/main.py').is_file()
    broker = (payload / 'usr/lib/systemd/system/oh-no-parent-control-broker.service').read_text()
    assert 'Group=wheel\n' in broker and 'Group=sudo' not in broker
    unit = configparser.ConfigParser(strict=False, interpolation=None)
    unit.read_string(broker)
    assert set(unit['Service']['RestrictAddressFamilies'].split()) == {'AF_UNIX', 'AF_NETLINK'}
    agent = (payload / 'usr/lib/systemd/user/oh-no-parent-control-polkit-agent.service').read_text()
    assert 'Type=simple\n' in agent
    assert 'ExecStart=/usr/libexec/polkit-mate-authentication-agent-1\n' in agent
    stack = (payload / 'usr/share/oh-no-parent-control/pam/managed-stack').read_text()
    assert 'ingroup wheel' in stack and 'ingroup sudo' not in stack
    assert stack.index('pam_malcontent.so') < stack.rindex('pam_oh_no_parent_control.so')
    assert stack.index('oh-no-parent-control-login-check') < stack.index('pam_malcontent.so')
    manifest = json.loads((payload / 'usr/share/oh-no-parent-control/package-activation.json').read_text())
    files = {entry['path']: entry for entry in manifest['files']}
    assert files['usr/lib64/security/pam_oh_no_parent_control.so']['activation'] == 'session-renewal'
    assert files['usr/share/oh-no-parent-control/pam/managed-stack']['activation'] == 'reboot'
    for relative, entry in files.items():
        assert entry['sha256'] == hashlib.sha256((payload / relative).read_bytes()).hexdigest()
    extension = payload / 'usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com'
    trust_path = 'usr/share/oh-no-parent-control/child-extension.trust'
    trust_lines = (payload / trust_path).read_text().splitlines()[1:]
    assert trust_lines == [f'/{path.relative_to(payload)} {path.stat().st_size} '
                           f'{hashlib.sha256(path.read_bytes()).hexdigest()}'
                           for path in sorted(extension.glob('*.mjs'))]
    assert {path.name for path in extension.glob('*.mjs')} == {
        'diagnosticEvents.mjs', 'indicatorLogic.mjs', 'gettext.mjs', 'languages.mjs',
    }
    assert files[trust_path]['activation'] == 'none'
    manuals = payload / 'usr/share/man/man1'
    for name in ('oh-no-parent-control.1', 'oh-no-parent-control-parent.1'):
        assert (manuals / name).read_bytes() == (ROOT / 'packaging/man' / name).read_bytes()
    assert (manuals / 'oh-no-parent-control-child.1').is_symlink()
    assert (manuals / 'oh-no-parent-control-child.1').readlink() == Path('oh-no-parent-control.1')


def test_fedora_pam_policy_tracks_both_shared_profiles(tmp_path):
    stage = runpy.run_path(str(ROOT / 'packaging/stage_distribution.py'))
    profiles = tmp_path / 'data/pam-configs'
    profiles.mkdir(parents=True)
    for name in ('oh-no-parent-control-kiosk-only', 'oh-no-parent-control-session-limits'):
        shutil.copy2(ROOT / 'data/pam-configs' / name, profiles / name)
    gate = profiles / 'oh-no-parent-control-kiosk-only'
    gate.write_text(gate.read_text().replace(' quiet ', ' quiet debug '))
    stack = stage['pam_stack'](tmp_path)
    assert stack.startswith('account required pam_exec.so quiet debug ')
    assert stack.index('oh-no-parent-control-login-check') < stack.index('success=5')
    assert 'ingroup wheel' in stack and 'ingroup sudo' not in stack
    gate.write_text('Name: empty profile\nAccount:\n')
    with pytest.raises(ValueError, match='empty managed PAM profile'):
        stage['pam_stack'](tmp_path)


def test_fedora_readiness_is_a_separate_required_boot_gate(fedora_payload):
    system = fedora_payload / 'usr/lib/systemd/system'
    # No additional process may inherit the daemon's SELinux-labelled runtime
    # directory. This is the integration that previously broke Fedora boot.
    assert not (system / 'fapolicyd.service.d/oh-no-parent-control-readiness.conf').exists()
    gate = configparser.ConfigParser(interpolation=None)
    gate.read(system / 'oh-no-parent-control-execution-policy-ready.service')
    assert gate['Unit']['Requires'] == 'fapolicyd.service'
    assert gate['Unit']['After'] == 'fapolicyd.service'
    assert gate['Unit']['PartOf'] == 'fapolicyd.service'
    assert gate['Service']['Type'] == 'oneshot'
    assert gate['Service']['ExecStart'] == '/usr/libexec/oh-no-parent-control-execution-policy-ready'
    assert gate['Service']['RemainAfterExit'] == 'yes'
    assert gate['Service']['TimeoutStartSec'] == '90s'
    assert 'RuntimeDirectory' not in gate['Service']
    assert 'ExecStartPost' not in gate['Service']
    display = configparser.ConfigParser(interpolation=None)
    display.read(system / 'display-manager.service.d/oh-no-parent-control.conf')
    assert display['Unit']['Requires'] == 'oh-no-parent-control-execution-policy-ready.service'
    assert display['Unit']['After'] == 'oh-no-parent-control-execution-policy-ready.service'
    assert (fedora_payload / 'usr/libexec/oh-no-parent-control-execution-policy-ready').read_bytes() == (
        ROOT / 'tools/execution_policy_ready.py').read_bytes()
    manifest = json.loads((fedora_payload / 'usr/share/oh-no-parent-control/package-activation.json').read_text())
    entries = {entry['path']: entry for entry in manifest['files']}
    assert entries['usr/lib/systemd/system/oh-no-parent-control-execution-policy-ready.service']['activation'] == 'reboot'
    canary = '00-oh-no-parent-control-canary.rules'
    rule = fedora_payload / 'usr/share/oh-no-parent-control' / canary
    assert rule.read_bytes() == (ROOT / 'data/fapolicyd' / canary).read_bytes()
    assert entries['usr/share/oh-no-parent-control/' + canary]['activation'] == 'reboot'
    # Fedora's known-libs default installs 42-trusted-elf.rules, whose execute
    # allow also matches trusted RPM-owned scripts. The canary must precede it.
    assert canary < '42-trusted-elf.rules'
    assert [line for line in rule.read_text().splitlines() if line and not line.startswith('#')] == [
        'deny perm=execute uid=0 : path=/usr/libexec/oh-no-parent-control-execution-policy-probe',
    ]
    spec = (ROOT / 'rpm/oh-no-parent-control.spec.in').read_text()
    assert '%{_unitdir}/oh-no-parent-control-execution-policy-ready.service\n' in spec
    assert '%{_unitdir}/fapolicyd.service.d/' not in spec


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora'])
def test_shared_source_check_rejects_broken_lifecycle_adapters(tmp_path, monkeypatch, distribution):
    monkeypatch.syspath_prepend(str(ROOT / 'packaging'))
    check = runpy.run_path(str(ROOT / 'packaging/check_package.py'))['check_lifecycle']
    shutil.copytree(ROOT / 'packaging', tmp_path / 'packaging')
    check(tmp_path)
    adapter = tmp_path / 'packaging' / f'{distribution}.inc'
    adapter.write_text(adapter.read_text().replace('# @pam_enable@\n', '# @pam_enable@\nif then\n'))
    with pytest.raises(ValueError, match=f'{distribution} postinst:'):
        check(tmp_path)


def test_reproducible_rpm_sources_use_the_same_allowlist_as_ppa(tmp_path):
    outputs = []
    for name in ('first', 'second'):
        workspace = tmp_path / name
        workspace.mkdir()
        top, spec, archive, identity = build_rpm.sources(ROOT, workspace, '0.1.dev')
        outputs.append((spec.read_bytes(), archive.read_bytes(), identity.read_bytes()))
        with tarfile.open(archive) as contents:
            selected = {Path(*Path(member.name).parts[1:]) for member in contents if member.isfile()}
            assert selected == set(package_inputs.paths(ROOT))
            assert all(member.uid == member.gid == 0 for member in contents)
        assert 'Release:        0.1.dev%{?dist}' in spec.read_text()
        assert not any(top.glob('RPMS/*/*.rpm'))
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize('release', ['../bad', '1;touch bad', '1%{evil}', '1-2', '', 'dev'])
def test_invalid_rpm_release_is_refused(release):
    with pytest.raises(ValueError, match='RPM release'):
        build_rpm.metadata(ROOT, release)


def test_missing_rpm_builder_preserves_sources_and_reports_failure(tmp_path, monkeypatch):
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    output = tmp_path / 'output/rpm'
    monkeypatch.setattr(build_rpm, 'scratch_directory', lambda: scratch)
    monkeypatch.setattr(build_rpm.shutil, 'which', lambda name: None)
    with pytest.raises(ValueError, match='builder is missing'):
        build_rpm.build(ROOT, output)
    assert (output / 'oh-no-parent-control.spec').is_file()
    assert len(list(output.glob('*.tar.xz'))) == 1
    assert not list(output.glob('*.rpm'))
    assert list(scratch.iterdir()) == []


@pytest.mark.parametrize('failed', [False, True])
def test_rpm_binary_build_uses_fedora_mock_and_retains_failure_evidence(tmp_path, monkeypatch, failed):
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    output = tmp_path / 'output/rpm'
    monkeypatch.setattr(build_rpm, 'scratch_directory', lambda: scratch)
    monkeypatch.setattr(build_rpm, 'scratch_descriptors', lambda: ())
    monkeypatch.setattr(build_rpm.shutil, 'which', lambda name: '/fixture/' + name)
    commands = []
    original_run = subprocess.run

    def run(arguments, **kwargs):
        if arguments[0] not in ('mock', 'rpmbuild'):
            return original_run(arguments, **kwargs)
        commands.append(arguments)
        if arguments[0] == 'rpmbuild':
            assert '-bs' in arguments and '-ba' not in arguments
            (kwargs['cwd'] / 'SRPMS/package.src.rpm').write_bytes(b'fixture srpm')
        else:
            assert arguments[1:3] == ['--root', 'fedora-44-x86_64']
            result = Path(arguments[-1])
            result.mkdir()
            (result / 'build.log').write_text('retained mock log')
            if failed:
                raise subprocess.CalledProcessError(7, arguments)
            (result / 'oh-no-parent-control-1.2-0.1.dev.fc44.x86_64.rpm').write_bytes(b'fixture fedora rpm')
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(build_rpm.subprocess, 'run', run)
    if failed:
        with pytest.raises(subprocess.CalledProcessError):
            build_rpm.build(ROOT, output)
    else:
        build_rpm.build(ROOT, output)
    assert [command[0] for command in commands] == ['rpmbuild', 'mock']
    assert (output / 'package.src.rpm').read_bytes() == b'fixture srpm'
    assert (output / 'build.log').read_text() == 'retained mock log'
    assert (output / 'oh-no-parent-control-1.2-0.1.dev.fc44.x86_64.rpm').exists() != failed
    assert list(scratch.iterdir()) == []


def test_rpm_export_preserves_substituted_artifact(tmp_path):
    source = tmp_path / 'source/package.rpm'
    source.parent.mkdir()
    source.write_bytes(b'new')
    output = tmp_path / 'output'
    output.mkdir()
    foreign = tmp_path / 'foreign'
    foreign.write_bytes(b'preserved')
    (output / 'package.rpm').symlink_to(foreign)
    with pytest.raises(ValueError, match='substituted RPM artifact'):
        build_rpm.export(source, output)
    assert foreign.read_bytes() == b'preserved'


def test_rpm_scriptlets_are_standalone_and_upgrade_removal_is_inert(tmp_path):
    renderer = runpy.run_path(str(ROOT / 'packaging/render_lifecycle.py'))
    renderer['rpm_scripts'](ROOT, tmp_path)
    for script in tmp_path.iterdir():
        result = subprocess.run(['/bin/sh', '-n', str(script)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, (script.name, result.stderr)
        assert '#ONPC-LIFECYCLE' not in script.read_text()
    for name in ('rpm-preun', 'rpm-postun'):
        result = subprocess.run(['/bin/sh', str(tmp_path / name), '1'],
                                capture_output=True, text=True, timeout=10, env={})
        assert result.returncode == 0
        assert result.stdout == result.stderr == ''


@pytest.mark.parametrize('state', ['active', 'activating', 'failed', 'inactive'])
def test_fedora_removal_clears_readiness_after_detaching_display_manager(machine, state):
    machine.baseline(active=True, enabled=True, rules='administrator policy\n')
    rule = machine.integration('fapolicyd-canary', 'etc/fapolicyd/rules.d/00-oh-no-parent-control-canary.rules')
    result = machine.run('postrm', 'remove', distribution='fedora', READINESS_STATE=state)
    assert result.returncode == 0, result.stderr
    assert not rule.exists()
    assert not (machine.root / 'var/lib/oh-no-parent-control/installed-fapolicyd-canary').exists()
    commands = machine.commands.splitlines()
    unit = 'oh-no-parent-control-execution-policy-ready.service'
    if state in ('active', 'activating'):
        cleanup = f'systemctl stop {unit}'
    elif state == 'failed':
        cleanup = f'systemctl reset-failed {unit}'
    else:
        assert f'systemctl stop {unit}' not in commands
        assert f'systemctl reset-failed {unit}' not in commands
        return
    assert commands.index('systemctl daemon-reload') < commands.index(cleanup)
    assert commands.index(cleanup) < commands.index('fapolicyd-cli --reload-rules')
    assert 'systemctl stop fapolicyd.service' not in commands
    assert not any('gdm.service' in command for command in commands)


def test_fedora_readiness_cleanup_failure_preserves_policy_baseline_for_retry(machine):
    machine.baseline(active=True, enabled=True, rules='administrator policy\n')
    result = machine.run('postrm', 'remove', distribution='fedora',
                         READINESS_STATE='active', READINESS_STOP_STATUS='9')
    assert result.returncode == 9
    assert (machine.root / 'var/lib/oh-no-parent-control/fapolicyd-before-install/complete').exists()
    assert 'fapolicyd-cli --reload-rules' not in machine.commands
    retry = machine.run('postrm', 'remove', distribution='fedora', READINESS_STATE='active')
    assert retry.returncode == 0, retry.stderr
    assert not (machine.root / 'var/lib/oh-no-parent-control/fapolicyd-before-install').exists()


def test_ubuntu_removal_does_not_touch_fedora_readiness(machine):
    result = machine.run('postrm', 'remove', READINESS_STATE='active', READINESS_STOP_STATUS='9')
    assert result.returncode == 0, result.stderr
    assert 'oh-no-parent-control-execution-policy-ready.service' not in machine.commands


@pytest.mark.parametrize('phase', ['prerm', 'postrm'])
@pytest.mark.parametrize('changed', ['content', 'symlink'])
def test_fedora_removal_preserves_modified_canary(machine, phase, changed):
    rule = machine.integration('fapolicyd-canary', 'etc/fapolicyd/rules.d/00-oh-no-parent-control-canary.rules')
    if changed == 'content':
        rule.write_text('administrator rule\n')
    else:
        rule.unlink()
        rule.symlink_to(machine.write('administrator-rule', 'administrator rule\n'))
    result = machine.run(phase, 'remove', distribution='fedora')
    assert result.returncode != 0
    assert rule.read_text() == 'administrator rule\n'
    assert 'systemctl stop' not in machine.commands
    assert 'fapolicyd-cli --reload-rules' not in machine.commands


def test_fedora_install_refuses_unowned_canary_before_package_effects(machine):
    machine.write('etc/os-release', 'ID=fedora\nVERSION_ID=44\nVARIANT_ID=workstation\n')
    machine.write('test-bin/authselect', '#!/bin/sh\ncase "$1" in current) echo local;; esac\n').chmod(0o755)
    rule = machine.write('etc/fapolicyd/rules.d/00-oh-no-parent-control-canary.rules', 'administrator rule\n')
    result = machine.run('preinst', 'install', distribution='fedora')
    assert result.returncode != 0
    assert 'canary path already exists' in result.stderr
    assert rule.read_text() == 'administrator rule\n'
    assert not machine.commands


@pytest.mark.parametrize('version,variant,accepted', [
    ('44', 'workstation', True), ('43', 'workstation', False),
    ('45', 'workstation', False), ('44', 'server', False), ('44', '', False),
])
def test_fedora_os_gate_precedes_package_effects(machine, version, variant, accepted):
    machine.write('etc/os-release', f'ID=fedora\nVERSION_ID={version}\nVARIANT_ID={variant}\n')
    machine.write('test-bin/authselect', '#!/bin/sh\ncase "$1" in current) echo local;; esac\n').chmod(0o755)
    result = machine.run('preinst', 'install', distribution='fedora')
    assert (result.returncode == 0) == accepted, result.stderr
    if not accepted:
        assert machine.commands == ''
        assert not (machine.root / 'var/lib/oh-no-parent-control/migration-in-progress').exists()


@pytest.mark.parametrize('package_machine', ['fedora'], indirect=True)
@pytest.mark.parametrize('failure', [None, 'migration', 'compile', 'reload', 'readiness', 'broker'])
def test_fedora_rpm_scriptlet_owns_configuration_and_preserves_failures(
    package_machine, tmp_path, failure,
):
    root, state, run = package_machine
    renderer = runpy.run_path(str(ROOT / 'packaging/render_lifecycle.py'))
    scripts = tmp_path / 'rpm-lifecycle'
    renderer['rpm_scripts'](ROOT, scripts)
    # Execute the actual RPM transaction callback with the existing isolated
    # service/account machine, without a Make installation or repair step.
    source = (scripts / 'rpm-posttrans').read_text()
    (root / 'postinst').write_text(relocate_system_paths(source, root))
    spec = (ROOT / 'rpm/oh-no-parent-control.spec.in').read_text()
    assert '%posttrans -f rpm-lifecycle/rpm-posttrans' in spec
    for dependency in ('authselect', 'fapolicyd', 'malcontent >= 0.14.0',
                       'malcontent-libs >= 0.14.0', 'malcontent-pam >= 0.14.0',
                       'policycoreutils', 'shadow-utils', 'systemd'):
        assert f'Requires:       {dependency}\n' in spec
    result = run(IMPACTS='process-restart\nreboot',
                 MIGRATION_STATUS='7' if failure == 'migration' else '0',
                 RULE_COMPILE_STATUS='10' if failure == 'compile' else '0',
                 RULE_RELOAD_STATUS='11' if failure == 'reload' else '0',
                 READINESS_STATUS='9' if failure == 'readiness' else '0',
                 BROKER_STATUS='8' if failure == 'broker' else '0')
    if failure:
        assert result.returncode == {'migration': 7, 'compile': 10, 'reload': 11,
                                     'readiness': 9, 'broker': 1}[failure]
        assert (state / 'package-activation-pending').exists()
        assert (state / 'previous-package-activation.json').exists()
        # Every pre-activation failure must retain the D-Bus startup exclusion.
        assert (state / 'migration-in-progress').exists() == (failure != 'broker')
        if failure in ('compile', 'reload', 'readiness'):
            assert 'systemctl --system restart oh-no-parent-control-broker.service' not in (root / 'commands').read_text()
            if failure != 'readiness':
                assert 'systemctl start oh-no-parent-control-execution-policy-ready.service' not in (root / 'commands').read_text()
            retry = run(IMPACTS='process-restart\nreboot')
            assert retry.returncode == 0, retry.stderr
            assert not (state / 'package-activation-pending').exists()
        return
    assert result.returncode == 0, result.stderr
    commands = (root / 'commands').read_text().splitlines()
    canary = '00-oh-no-parent-control-canary.rules'
    assert (root / 'etc/fapolicyd/rules.d' / canary).read_bytes() == (ROOT / 'data/fapolicyd' / canary).read_bytes()
    assert (state / 'installed-fapolicyd-canary').read_bytes() == (ROOT / 'data/fapolicyd' / canary).read_bytes()
    assert commands.index('oh-no-parent-control-migrate-state ') < commands.index('oh-no-parent-control-fedora-pam install')
    assert 'systemd-sysusers malcontent-timer-extension-agent.conf malcontent-timerd.conf malcontent-webd.conf' in commands
    assert 'systemctl enable fapolicyd.service malcontent-timerd.service malcontent-timer-extension-agent.service' in commands
    assert 'systemctl start fapolicyd.service malcontent-timerd.service malcontent-timer-extension-agent.service' in commands
    readiness = 'systemctl start oh-no-parent-control-execution-policy-ready.service'
    assert commands.index('systemctl start fapolicyd.service malcontent-timerd.service malcontent-timer-extension-agent.service') < commands.index(readiness)
    assert commands.index('fagenrules ') < commands.index('fapolicyd-cli --reload-rules')
    assert commands.index('fapolicyd-cli --reload-rules') < commands.index(readiness)
    assert commands.index(readiness) < commands.index('systemctl --system restart oh-no-parent-control-broker.service')
    assert any(command.startswith('oh-no-parent-control-provision --kiosk-user ') for command in commands)
    assert any(command.startswith('restorecon -R ') for command in commands)
    assert 'systemctl --system restart oh-no-parent-control-broker.service' in commands
    assert (root / 'etc/gdm/PreSession/Default').read_bytes() == (state / 'installed-gdm-presession').read_bytes()
    assert not any('pam-auth-update' in command or 'deb-systemd-invoke' in command for command in commands)
    assert not (state / 'package-activation-pending').exists()
    assert (root / 'run/oh-no-parent-control-reboot-required').is_file()
    assert 'REBOOT REQUIRED' in result.stderr
    assert 'oh-no-parent-control: broker activation: restart' in result.stderr


def test_debian_wrapper_inlining_preserves_debhelper_boundary(tmp_path):
    renderer = runpy.run_path(str(ROOT / 'packaging/render_lifecycle.py'))
    staging = tmp_path / 'DEBIAN'
    staging.mkdir()
    for phase in renderer['PHASES']:
        source = (ROOT / 'debian' / phase).read_text().replace('#DEBHELPER#', 'echo debhelper-boundary')
        (staging / phase).write_text(source)
    renderer['expand_debian'](ROOT, tmp_path)
    script = (staging / 'postinst').read_text()
    assert script.index('echo debhelper-boundary') < script.index('oh-no-parent-control-package-notice --configured')
    assert '#ONPC-LIFECYCLE' not in script
    for phase in renderer['PHASES']:
        assert subprocess.run(['/bin/sh', '-n', str(staging / phase)], timeout=10).returncode == 0


def test_spec_hashes_final_payload_and_copr_does_not_publish():
    spec = (ROOT / 'rpm/oh-no-parent-control.spec.in').read_text()
    assert '%global onpc_spec_install_post %{macrobody:__spec_install_post}' in spec
    assert '%define __spec_install_post %{onpc_spec_install_post}' in spec
    assert '_generate-package-activation-manifest' in spec
    assert 'GENERATE_ACTIVATION_MANIFEST=0' in spec
    assert 'Requires(postun): fapolicyd' in spec
    assert 'BuildRequires:  systemd-rpm-macros' in spec
    copr = (ROOT / '.copr/Makefile').read_text()
    assert '--srpm --output "$(outdir)"' in copr
    assert 'copr-cli' not in copr


@pytest.mark.parametrize('prerequisite_status', [0, 7])
def test_copr_make_entrypoint_exports_srpm_without_host_setup(tmp_path, prerequisite_status):
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    package_inputs.copy(ROOT, checkout)
    # COPR checks out the repository, including the source-preparation tools;
    # these development helpers must remain absent from the product tarball.
    for name in ('build_rpm.py', 'rpm_builder.py', 'package_inputs.py',
                 'test_storage.py', 'test_retention.py'):
        shutil.copy2(ROOT / 'tools' / name, checkout / 'tools' / name)
    (checkout / '.copr').mkdir()
    shutil.copy2(ROOT / '.copr/Makefile', checkout / '.copr/Makefile')
    commands = tmp_path / 'commands'
    commands.mkdir()
    (commands / 'dnf').write_text(
        '#!/bin/sh\n[ "$*" = "-y install python3 rpm-build" ] || exit 99\n'
        f'exit {prerequisite_status}\n')
    (commands / 'rpmbuild').write_text('''#!/usr/bin/python3
import pathlib, sys
args = sys.argv[1:]
assert '-bs' in args and '-ba' not in args
top = pathlib.Path(args[args.index('--define') + 1].removeprefix('_topdir '))
assert list((top / 'SOURCES').glob('*.tar.xz'))
assert (top / 'SPECS/oh-no-parent-control.spec').is_file()
(top / 'SRPMS/oh-no-parent-control.src.rpm').write_bytes(b'fixture srpm')
''')
    for command in commands.iterdir():
        command.chmod(0o755)
    output = tmp_path / 'copr output'
    result = subprocess.run(
        ['make', '-f', '.copr/Makefile', 'srpm', f'outdir={output}',
         'spec=rpm/oh-no-parent-control.spec.in'], cwd=checkout,
        env=os.environ | {'PATH': f'{commands}:/usr/bin:/bin'},
        capture_output=True, text=True, timeout=60)
    if prerequisite_status:
        assert result.returncode != 0
        assert not output.exists()
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert (output / 'oh-no-parent-control.src.rpm').read_bytes() == b'fixture srpm'
        archive, = output.glob('*.tar.xz')
        with tarfile.open(archive) as contents:
            assert not any(member.name.endswith('/tools/test_storage.py') for member in contents)


def test_container_recipe_tracks_build_dependencies_without_freezing_runtime_edits(tmp_path):
    (tmp_path / 'rpm').mkdir()
    recipe = tmp_path / 'rpm/Containerfile'
    spec = tmp_path / 'rpm/oh-no-parent-control.spec.in'
    recipe.write_bytes((ROOT / 'rpm/Containerfile').read_bytes())
    original = (ROOT / 'rpm/oh-no-parent-control.spec.in').read_text()
    spec.write_text(original)
    first = rpm_builder.inputs(tmp_path)
    assert '@VERSION@' not in first[1] and '@RELEASE@' not in first[1]
    spec.write_text(original.replace('Requires:       accountsservice', 'Requires:       accountsservice >= 1'))
    assert rpm_builder.inputs(tmp_path)[2] == first[2]
    spec.write_text(original + '\nBuildRequires: extra-devel\n')
    assert rpm_builder.inputs(tmp_path)[2] != first[2]


def test_setup_prepares_a_private_container_context_and_propagates_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(rpm_builder, 'scratch_directory', lambda: tmp_path)
    monkeypatch.setattr(rpm_builder, 'scratch_descriptors', lambda: ())
    monkeypatch.setattr(rpm_builder.shutil, 'which', lambda name: '/fixture/' + name)
    commands = []

    def run(arguments, **kwargs):
        commands.append(arguments)
        if arguments[1] == 'build':
            context = Path(arguments[-1])
            assert {p.name for p in context.iterdir()} == {'Containerfile', 'oh-no-parent-control.spec'}
            assert 'dnf -y builddep' in (context / 'Containerfile').read_text()
            assert 'BuildRequires:  systemd-rpm-macros' in (context / 'oh-no-parent-control.spec').read_text()
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(rpm_builder.subprocess, 'run', run)
    rpm_builder.setup(ROOT)
    assert [command[1] for command in commands] == ['build', 'image']
    assert list(tmp_path.iterdir()) == []

    def fail(arguments, **kwargs):
        raise subprocess.CalledProcessError(9, arguments)

    monkeypatch.setattr(rpm_builder.subprocess, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        rpm_builder.setup(ROOT)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('empty', [False, True])
def test_container_binary_build_is_offline_and_requires_a_product_rpm(tmp_path, monkeypatch, empty):
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    output = tmp_path / 'output'
    monkeypatch.setattr(build_rpm, 'scratch_directory', lambda: scratch)
    monkeypatch.setattr(build_rpm, 'scratch_descriptors', lambda: ())
    monkeypatch.setattr(build_rpm, 'native_fedora44', lambda: False)
    monkeypatch.setattr(build_rpm.shutil, 'which', lambda name: None if name == 'mock' else '/fixture/' + name)
    monkeypatch.setattr(rpm_builder, 'require_image', lambda root: 'localhost/fixture:fc44')
    original_run = subprocess.run
    commands = []

    def run(arguments, **kwargs):
        if arguments[0] != 'podman':
            return original_run(arguments, **kwargs)
        commands.append(arguments)
        assert '--network=none' in arguments and '--pull=never' in arguments
        assert '--userns=keep-id' in arguments and '--cap-drop=all' in arguments
        assert '--privileged' not in arguments
        top = kwargs['cwd']
        (top / 'SRPMS/package.src.rpm').write_bytes(b'fixture srpm')
        if not empty:
            binaries = top / 'RPMS/x86_64'
            binaries.mkdir()
            (binaries / 'oh-no-parent-control-1.2-0.1.dev.fc44.x86_64.rpm').write_bytes(b'fixture rpm')
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(build_rpm.subprocess, 'run', run)
    if empty:
        with pytest.raises(ValueError, match='no product binary RPM'):
            build_rpm.build(ROOT, output)
    else:
        build_rpm.build(ROOT, output)
        assert (output / 'oh-no-parent-control-1.2-0.1.dev.fc44.x86_64.rpm').read_bytes() == b'fixture rpm'
    assert len(commands) == 1
    assert (output / 'build.log').is_file()
    assert list(scratch.iterdir()) == []
