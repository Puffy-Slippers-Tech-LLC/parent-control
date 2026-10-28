"""Private decoder/evidence files and waited Perl; no live VM, bus or account."""
import copy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import check_graphical_smoke as smoke
import package_command as command
import package_install
import package_upgrade as upgrade
import session_control
from owned_commands import CommandError
from private_artifacts import EvidenceError
from tests.support.desktop_session import props


@pytest.fixture(autouse=True)
def platform(monkeypatch):
    monkeypatch.setattr(command.session_control, 'package_format', lambda: 'deb')

PACKAGES = {label: {'name': 'oh-no-parent-control', 'architecture': 'amd64',
    'version': version, 'sha256': digest} for label, version, digest in (
        ('previous', '1.2+ppa1~ubuntu26.04.1', 'a' * 64),
        ('current', '1.3+ppa1~ubuntu26.04.1', 'b' * 64))}
BEFORE, AFTER = 'c' * 64, 'd' * 64


def boundary(monkeypatch, version=None, boot=BEFORE):
    value = {'version': version, 'boot': boot, 'session': '7',
        'packages': {label: item['sha256'] for label, item in PACKAGES.items()},
        'preserved': {'accounts': {'parent': {'language': 'en_US.UTF-8'}},
                      'system_locale': ['LANG=en_US.UTF-8'], 'files': {'witness': 'e' * 64}}}
    transport = SimpleNamespace(config={'run': 'attempt', 'domain_uuid': 'vm'},
        commands=SimpleNamespace(last_returncode=0), guard=Mock())
    def call(argv, **options):
        if len(argv) == 4:
            return (json.dumps(value, sort_keys=True) + '\n').encode()
        label = 'previous' if argv[3] == command.OLD_INSTALL else 'current'
        assert argv[4] == PACKAGES[label]['sha256']
        assert json.loads(argv[5]) == PACKAGES
        value['version'] = PACKAGES[label]['version']
        return (command.COMPLETE + '\n' + command.NOTICE + '\n').encode()
    transport.call = Mock(side_effect=call)
    verified = SimpleNamespace(inputs={'package_sha256': PACKAGES['current']['sha256']},
        asset_files={'package.deb': PACKAGES['current']['sha256']},
        upgrade_inputs={'packages': copy.deepcopy(PACKAGES)}, recheck=Mock())
    monkeypatch.setattr(session_control, 'observe', Mock(return_value={
        'outcome': 'passed', 'package_sha256': PACKAGES['current']['sha256']}))
    return command.PackageCommand(transport, verified), value


@pytest.mark.parametrize('extra', [{}, {'install': True}, {'package_install': True},
    {'customer_reboot': True}, {'upgrade_assets': True}, {'challenges': True},
    {'independent_network': True}, {'approval_flow': 'rejection'}, {'fresh_desktop': 'parent'}])
def test_product_free_exclusive_gate(extra):
    options = dict(assets='inputs', provision_credentials=True, **extra) if extra else {}
    with pytest.raises(CommandError): smoke.main(package_upgrade=True, **options)


@pytest.mark.parametrize('binding', [command.OLD_INSTALL, command.UPGRADE])
@pytest.mark.parametrize('fault', ['digest', 'attempt', 'vm', 'phase', 'entry'])
def test_wrong_release_entry_never_submits(monkeypatch, binding, fault):
    item, value = boundary(monkeypatch, PACKAGES['previous']['version'] if binding == command.UPGRADE else None)
    digest = PACKAGES['previous' if binding == command.OLD_INSTALL else 'current']['sha256']
    identity = dict(item.identity)
    if fault == 'digest': digest = 'f' * 64
    if fault == 'attempt': identity['run'] = 'other'
    if fault == 'vm': identity['domain_uuid'] = 'other'
    if fault == 'phase': value['version'] = PACKAGES['current']['version']
    if fault == 'entry': session_control.observe.side_effect = EvidenceError('wrong-entry')
    with pytest.raises(EvidenceError): item.submit(binding, digest, identity)
    assert not item.attempted
    assert not any(len(call.args[0]) == 6 for call in item.transport.call.call_args_list)


@pytest.mark.parametrize('binding', [command.OLD_INSTALL, command.UPGRADE])
@pytest.mark.parametrize('fault', ['timeout', 'lost', 'output', 'success'])
def test_uncertainty_consumed_across_command_objects(monkeypatch, binding, fault):
    item, _ = boundary(monkeypatch, PACKAGES['previous']['version'] if binding == command.UPGRADE else None)
    real = item.transport.call.side_effect
    def call(argv, **options):
        if len(argv) == 4: return real(argv, **options)
        if fault == 'timeout': raise TimeoutError()
        if fault == 'lost': raise RuntimeError('lost')
        if fault == 'output': options['on_output'](b'x' * (command.LIMIT + 1))
        return real(argv, **options)
    item.transport.call.side_effect = call
    digest = PACKAGES['previous' if binding == command.OLD_INSTALL else 'current']['sha256']
    if fault == 'success': item.submit(binding, digest, item.identity)
    else:
        with pytest.raises((TimeoutError, RuntimeError, EvidenceError)): item.submit(binding, digest, item.identity)
    second = command.PackageCommand(item.transport, item.verified)
    with pytest.raises(EvidenceError, match='package:replay'): second.submit(binding, digest, second.identity)
    assert sum(len(call.args[0]) == 6 for call in item.transport.call.call_args_list) == 1


@pytest.mark.parametrize('fault', ['', 'old-digest', 'extra', 'bound', 'owner'])
def test_actual_identity_decoder_binds_nondefault_package(monkeypatch, fault):
    item, value = boundary(monkeypatch)
    if fault == 'old-digest': value['packages']['previous'] = 'f' * 64
    if fault == 'extra': value['private-state'] = 'forbidden'
    if fault == 'bound': item.transport.call.side_effect = None; item.transport.call.return_value = b'x' * 65537
    if fault == 'owner': item.transport.config['run'] = 'other'
    if fault:
        with pytest.raises((EvidenceError, ValueError)): item.read_identity()
    else:
        assert item.read_identity() == value
        assert item.read_identity() == value
        compile(command.guest_source(read=True), '<package-read>', 'exec')
        compile(command.guest_source(), '<package-submit>', 'exec')


@pytest.mark.parametrize('binding', [command.OLD_INSTALL, command.UPGRADE])
@pytest.mark.parametrize('fault', ['', 'greeter', 'digest', 'phase', 'replay'])
def test_guest_single_use_before_real_argv(monkeypatch, tmp_path, binding, fault):
    import grp
    import pwd
    monkeypatch.setattr(os, 'geteuid', lambda: 0)
    monkeypatch.setattr(pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name='fixture'))
    monkeypatch.setattr(grp, 'getgrnam', lambda _: SimpleNamespace(gr_gid=27))
    monkeypatch.setattr(os, 'getgrouplist', lambda *_: [27])
    monkeypatch.setattr(session_control, 'sessions', lambda: {'7': props(kind='greeter' if fault == 'greeter' else 'user')})
    label = 'previous' if binding == command.OLD_INSTALL else 'current'
    digest = PACKAGES[label]['sha256']
    monkeypatch.setattr(session_control, 'package_digest', lambda *_: 'f' * 64 if fault == 'digest' else digest)
    monkeypatch.setattr(command, 'guest_phase', Mock(return_value=BEFORE,
        side_effect=EvidenceError('phase') if fault == 'phase' else None))
    marker = tmp_path / 'used'
    if fault == 'replay': marker.touch()
    opening = os.open
    def open_marker(path, flags, mode):
        assert path == '/var/lib/onpc-e2e-assets/' + (
            '.previous-install-used' if binding == command.OLD_INSTALL else '.package-upgrade-used')
        return opening(marker, flags, mode)
    monkeypatch.setattr(os, 'open', open_marker)
    monkeypatch.setattr(os, 'environ', {})
    monkeypatch.setattr(os, 'dup2', Mock())
    execute = Mock()
    monkeypatch.setattr(os, 'execv', execute)
    if fault:
        with pytest.raises((EvidenceError, session_control.SessionError, FileExistsError)):
            command.guest_submit(binding, digest, PACKAGES)
        execute.assert_not_called()
    else:
        command.guest_submit(binding, digest, PACKAGES)
        assert execute.call_args.args[1][-1] == '/var/lib/onpc-e2e-assets/' + (
            'previous/package.deb' if binding == command.OLD_INSTALL else 'package.deb')
        assert marker.read_text() == BEFORE
        with pytest.raises(FileExistsError): command.guest_submit(binding, digest, PACKAGES)
        assert execute.call_count == 1


def test_live_wrong_entry_reuses_command_and_reboot_refusal(tmp_path, monkeypatch):
    item, _ = boundary(monkeypatch)
    journey = upgrade.PackageUpgradeJourney(SimpleNamespace(directory=tmp_path,
        product_free=True, asset_transfer=Mock(), verified=item.verified), Mock())
    journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}]
    journey.transport = item.transport
    result = upgrade.entry_refusal(journey, Mock())
    assert result['package_entry_refused'] and result['reboot_refused']
    item.transport.call.assert_not_called()


@pytest.mark.parametrize('binding', [command.OLD_INSTALL, command.UPGRADE])
@pytest.mark.parametrize('fault', ['', 'metadata', 'bytes', 'installed', 'same-boot', 'marker'])
def test_actual_guest_phase_metadata_digest_and_activation(monkeypatch, tmp_path, binding, fault):
    import subprocess
    boot_file = tmp_path / 'boot'
    boot_file.write_bytes(b'new-boot\n')
    new_boot = hashlib.sha256(boot_file.read_bytes()).hexdigest()
    marker = tmp_path / 'marker'
    marker.write_text(new_boot if fault == 'same-boot' else '' if fault == 'marker' else BEFORE)
    marker.chmod(0o600)
    original_path = Path
    class MarkerPath(type(marker)):
        def lstat(self):
            info = super().lstat()
            return SimpleNamespace(st_uid=0, st_nlink=info.st_nlink, st_mode=info.st_mode)
    def path(value):
        if value == '/proc/sys/kernel/random/boot_id': return boot_file
        if value.endswith('.previous-install-used'): return MarkerPath(marker)
        return original_path(value)
    monkeypatch.setattr(__import__('pathlib'), 'Path', path)
    def metadata(argv, **options):
        label = 'previous' if '/previous/' in argv[2] else 'current'
        item = PACKAGES[label]
        return ('Package: ' + ('substituted' if fault == 'metadata' else item['name']) +
                '\nVersion: ' + item['version'] + '\nArchitecture: amd64\n').encode()
    monkeypatch.setattr(subprocess, 'check_output', metadata)
    status = 1 if binding == command.OLD_INSTALL else 0
    if fault == 'installed': status = 1 - status
    installed = PACKAGES['previous']['version']
    def run(argv, **options):
        if argv[0] == '/usr/bin/dpkg': return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=status, stdout=(
            f'install ok installed\n{installed}\n'.encode() if status == 0 else b''))
    monkeypatch.setattr(subprocess, 'run', run)
    monkeypatch.setattr(session_control, 'package_digest', lambda label:
        'f' * 64 if fault == 'bytes' else PACKAGES[label]['sha256'])
    applicable = fault not in ('same-boot', 'marker') or binding == command.UPGRADE
    if fault and applicable:
        with pytest.raises(session_control.SessionError): command.guest_phase(binding, PACKAGES)
    else:
        assert command.guest_phase(binding, PACKAGES) == new_boot
