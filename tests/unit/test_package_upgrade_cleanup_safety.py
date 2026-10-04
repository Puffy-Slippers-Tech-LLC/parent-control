"""Private decoder/evidence files and waited Perl; no live VM, bus or account."""
import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import check_e2e_package_upgrade as selector
import check_graphical_smoke as smoke
import installed_journey
import package_command as command
import package_install
import package_upgrade as upgrade
import session_control
from owned_commands import CommandError
from private_artifacts import EvidenceError
from tests.support.desktop_session import RUN_PROBE, props
from tests.support.perl import run_perl
from tests.support.e2e_evidence import attempt
from tests.support.e2e_recording import session


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


def test_selector_and_automatic_asset_preparation(monkeypatch):
    import tools.test_commands as launchers
    launch = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', launch)
    assert selector.main() == 0
    launch.assert_called_once_with(assets=selector.ASSETS, provision_credentials=True, package_upgrade=True)
    monkeypatch.setattr(launchers.os.path, 'lexists', lambda _: False)
    allocate = Mock(return_value=str(selector.ASSETS))
    monkeypatch.setattr(launchers, 'allocate_artifact_output', allocate)
    result = launchers.qualification_artifact_command(Path.cwd(), 'integration', ['check_e2e_package_upgrade'])
    assert '--upgrade-inputs' in result and result[-1] == str(selector.ASSETS)


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


@pytest.mark.parametrize('fault', ['', 'artifact', 'metadata', 'old-digest', 'extra', 'owner'])
@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_current_only_identity_has_no_old_package_dependency(monkeypatch, tmp_path, fault, package_format):
    import build_test_artifacts
    item, value = boundary(monkeypatch)
    item.verified.upgrade_inputs = None
    item.verified.assets = tmp_path
    item.verified.asset_files = {'package.' + package_format: PACKAGES['current']['sha256']}
    metadata = copy.deepcopy(PACKAGES['current'])
    if package_format == 'rpm':
        metadata.update(architecture='x86_64', version='0:1.3-0.1.dev.fc44')
    if fault == 'artifact': metadata['sha256'] = 'f' * 64
    if fault == 'metadata': metadata['name'] = 'foreign-package'
    read = Mock(return_value=metadata)
    monkeypatch.setattr(build_test_artifacts, 'package_identity', read)
    value['packages'] = {'current': PACKAGES['current']['sha256']}
    if fault == 'old-digest': value['packages']['previous'] = 'a' * 64
    if fault == 'extra': value['private'] = 'forbidden'
    if fault == 'owner': item.transport.config['run'] = 'foreign'
    if fault:
        with pytest.raises(EvidenceError): item.read_identity()
    else:
        assert item.read_identity() == value
        read.assert_called_once_with(tmp_path / ('package.' + package_format))
        assert json.loads(item.transport.call.call_args.args[0][-1]) == {'current': metadata}


@pytest.mark.parametrize('fault', ['', 'version', 'boot', 'session', 'preservation', 'inputs',
                                 'unstable', 'notice', 'missing', 'not-fresh'])
def test_current_install_independently_requires_version_notice_boot_and_preservation(monkeypatch, fault):
    item, before = boundary(monkeypatch)
    before['packages'] = {'current': PACKAGES['current']['sha256']}
    before = copy.deepcopy(before)
    if fault == 'not-fresh': before['version'] = PACKAGES['current']['version']
    after = copy.deepcopy(before)
    after['version'] = PACKAGES['current']['version']
    after['preserved']['accounts']['new-package-account'] = {'language': 'en'}
    item.binding = command.BINDING
    item.receipt = ((command.COMPLETE + '\n' + command.NOTICE + '\n').encode(), 0)
    item.package_identities = Mock(return_value={'current': PACKAGES['current']})
    if fault == 'version': after['version'] = PACKAGES['previous']['version']
    if fault == 'boot': after['boot'] = AFTER
    if fault == 'session': after['session'] = 'changed'
    if fault == 'preservation': after['preserved']['accounts']['parent']['language'] = 'zh_CN'
    if fault == 'inputs': after['packages']['current'] = 'f' * 64
    if fault == 'notice': item.receipt = ((command.COMPLETE + '\n').encode(), 0)
    if fault == 'missing': item.receipt = None
    second = copy.deepcopy(after)
    if fault == 'unstable': second['boot'] = AFTER
    item.read_identity = Mock(side_effect=[after, second])
    if fault:
        with pytest.raises(EvidenceError): package_install.observe_current_install(item, before)
    else:
        result = package_install.observe_current_install(item, before)
        assert result['installed_version'] == PACKAGES['current']['version']
        assert result['notice'] == command.NOTICE and result['boot_sha256'] == BEFORE
        assert result['independent_readback'] and result['preservation_verified']
        assert item.read_identity.call_count == 2


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


@pytest.mark.parametrize('fault', ['', 'version', 'boot', 'session', 'preservation',
    'file-created', 'file-removed', 'file-changed', 'notice', 'trailing'])
def test_upgrade_result_before_durable_reply(tmp_path, monkeypatch, fault):
    item, value = boundary(monkeypatch, PACKAGES['previous']['version'], AFTER)
    value['preserved']['files']['/etc/motd'] = None if fault == 'file-created' else 'f' * 64
    before = copy.deepcopy(value)
    item.submit(command.UPGRADE, PACKAGES['current']['sha256'], item.identity)
    if fault == 'version': value['version'] = PACKAGES['previous']['version']
    if fault == 'boot': value['boot'] = 'e' * 64
    if fault == 'session': value['session'] = '8'
    if fault == 'preservation': value['preserved']['system_locale'] = ['LANG=other']
    if fault == 'file-created': value['preserved']['files']['/etc/motd'] = 'f' * 64
    if fault == 'file-removed': value['preserved']['files']['/etc/motd'] = None
    if fault == 'file-changed': value['preserved']['files']['/etc/motd'] = 'e' * 64
    if fault == 'notice': item.receipt = (command.COMPLETE.encode(), 0)
    if fault == 'trailing': item.receipt = (item.receipt[0] + b'later\n', 0)
    journey = upgrade.PackageUpgradeJourney(SimpleNamespace(directory=tmp_path,
        product_free=True, asset_transfer=Mock(), verified=item.verified), Mock())
    journey.transport = item.transport
    journey.upgrade_package, journey.activated_entry = item, before
    stage = 'upgrade-result'
    journey.steps = [{'stage': s} for s in upgrade.PLAN.stages[:upgrade.PLAN.stages.index(stage)]]
    journey.boot = AFTER
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': AFTER}))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        observed = journey.progress.call_args.args[1]
        assert observed['package']['installed_version'] == PACKAGES['current']['version']
        assert observed['package']['notice'] == command.NOTICE


@pytest.mark.parametrize('fault', ['', *upgrade.PLAN.screen_tags])
def test_worker_exact_order_and_refusal_stop(fault):
    source = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_customer_reboot;')
    source = source.replace('onpc_desktop_session::run', 'onpc_customer_reboot::run_upgrade')
    source = source.replace('}, $action);', "}, [qw(reboot-installed-greeter reboot-parent-focused "
        "reboot-recipient-qualified reboot-recipient-rechecked reboot-desktop)], "
        "{'after-reboot' => ['parent', 'reboot-recipient-qualified', 'reboot-recipient-rechecked']});")
    source = source.replace("push @events, ['stage', $_[0]];", """
        push @events, ['stage', $_[0]];
        die 'refusal' if $_[0] eq $action;
        return {observed => $_[0], ui_focused => 1} if $_[0] eq 'reboot-installed-greeter';
        return {observed => $_[0], challenge => {id => 'after-reboot', role => 'parent',
            surface => 'gdm', check => $_[0] =~ /rechecked$/ ? 'rechecked' : 'qualified'}}
            if $_[0] =~ /^reboot-recipient-/;
    """)
    source = source.replace('sub record_info { }', "sub record_info { push @main::events, ['title', $_[0]]; }")
    result = json.loads(run_perl(source, fault).stdout)
    assert bool(result['ok']) == (not fault)
    expected = list(upgrade.PLAN.screen_tags)
    expected = expected[:expected.index(fault) + 1] if fault else expected
    assert [event[1] for event in result['events'] if event[0] == 'stage'] == expected
    assert [event[1] for event in result['events'] if event[0] == 'title' and event[1] != 'shutdown'] == [
        'package-upgrade-' + stage for stage in expected]
    if not fault:
        assert result['events'].count(['secret']) == 2
        assert [event for event in result['events'] if event[0] != 'title'][-1] == ['power', 'off']


@pytest.mark.parametrize('fault', ['', 'decoder', 'durability'])
def test_custom_journey_through_real_recorder_and_worker_startup(session, tmp_path, monkeypatch, fault):
    item, value = boundary(monkeypatch, PACKAGES['previous']['version'], AFTER)
    before = copy.deepcopy(value)
    item.submit(command.UPGRADE, PACKAGES['current']['sha256'], item.identity)
    expected = session.payload['assertions'][0]
    tags = {stage: 'system:parent-command-context' for stage in (
        'preflight-start', 'preflight-one', 'preflight-two', 'upgrade-result')}
    plan = replace(upgrade.PLAN, screen_tags=tags,
        phases={'ready': 'setup', 'setup-detached': 'setup', 'preflight-start': 'start',
                'preflight-one': 'step-1', 'preflight-two': 'step-2', 'upgrade-result': expected['step_id']},
        assertions_after={'upgrade-result': expected['assertion_id']}, stage_actions={},
        invocations=(), challenges={}, reboot_transition=(), advance_after={})
    context = SimpleNamespace(directory=tmp_path / 'journey', verified=item.verified,
        product_free=True, asset_transfer=Mock(), credentials=Mock(), lease=Mock(), guestfs=Mock(), commands=Mock())
    context.directory.mkdir()
    recorder = session.recorder
    recorder.begin_case('E2E-001/gdm-observation')
    if fault == 'decoder': value['packages']['previous'] = 'f' * 64
    save = session.collector.save_report
    def save_report(name, report):
        if fault == 'durability' and report.get('event') == 'observation' and report.get('active_step') == expected['step_id']:
            raise OSError('write failed')
        return save(name, report)
    monkeypatch.setattr(session.collector, 'save_report', save_report)
    def worker(**options):
        journey = options['guarded_observe'].__self__
        assert isinstance(journey, upgrade.PackageUpgradeJourney)
        journey.transport, journey.vm, journey.boot = item.transport, SimpleNamespace(
            read=Mock(return_value={'boot_sha256': AFTER})), AFTER
        journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}]
        journey.upgrade_package, journey.activated_entry = item, before
        for stage in tags:
            path = context.directory / (stage + '.request.json')
            path.write_text(json.dumps({'stage': stage, 'screenshot': None}))
            options['guarded_observe'](Mock())
            assert (context.directory / (stage + '.reply.json')).exists()
        # Complete the synthetic fixture's unrelated recorder obligations;
        # these explicit doubles are never installed acceptance evidence.
        for assertion in session.payload['assertions'][1:]:
            ref = recorder.artifact('synthetic-' + assertion['assertion_id'],
                {'visible': 'screen', 'backend': 'backend', 'other_user': 'other-user'}[assertion['kind']],
                b'explicit synthetic fixture result', reviewed=True)
            recorder.assertion(assertion['assertion_id'], artifact_ids=[ref])
        return dict(outcome='passed', shutdown_verified=True, worker_stopped=True, callback_closed=True)
    context.run_worker = worker
    monkeypatch.setattr(upgrade.PackageUpgradeJourney, 'validate', lambda _: [])
    if fault:
        with pytest.raises((EvidenceError, OSError)):
            installed_journey.record_installed_journey(recorder, context, plan, actions={},
                journey_type=upgrade.PackageUpgradeJourney)
        assert not (context.directory / 'upgrade-result.reply.json').exists()
    else:
        installed_journey.record_installed_journey(recorder, context, plan, actions={},
            journey_type=upgrade.PackageUpgradeJourney)
        assert recorder.records[0]['assertions'][0]['assertion_id'] == expected['assertion_id']


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


@pytest.mark.parametrize('file_state', ['present', 'absent', 'denied',
    'hostname-missing', 'machine-id-missing'])
@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_public_account_reader_and_realistic_decoder_payload(monkeypatch, tmp_path, file_state, package_format):
    import account_language_guest as languages
    import pwd
    import subprocess
    monkeypatch.setattr(session_control, 'package_format', lambda: package_format)
    users = [pwd.struct_passwd((f'fixture-{n}', 'x', 1000 + n, 1000 + n,
        'Synthetic fixture', f'/home/fixture-{n}', '/bin/bash')) for n in range(120)]
    api = Mock(resolve=Mock(side_effect=lambda account: ('/org/freedesktop/Accounts/User' +
        str(account.pw_uid), 'en_US.UTF-8')))
    monkeypatch.setattr(languages, 'AccountsAPI', lambda: api)
    monkeypatch.setattr(languages, 'accounts', lambda: users)
    monkeypatch.setattr(languages, 'system_locale', lambda: ['LANG=en_US.UTF-8'])
    monkeypatch.setattr(os, 'getgrouplist', lambda *_: [1000, 27])
    monkeypatch.setattr(pwd, 'getpwnam', lambda _: users[0])
    monkeypatch.setattr(session_control, 'sessions', lambda: {'7': props()})
    monkeypatch.setattr(session_control, 'package_digest', lambda label: PACKAGES[label]['sha256'])
    def query(argv, **options):
        assert options['env']['LC_ALL'] == 'C'
        assert argv[0] == ('/usr/bin/rpm' if package_format == 'rpm' else '/usr/bin/dpkg-query')
        return SimpleNamespace(returncode=0, stdout=((
            'oh-no-parent-control' if package_format == 'rpm' else 'install ok installed') +
            '\n' + PACKAGES['previous']['version'] + '\n' + (
                'x86_64\n' if package_format == 'rpm' else '')).encode())
    monkeypatch.setattr(subprocess, 'run', query)
    witness = tmp_path / 'witness'
    witness.write_bytes(b'public preservation fixture\n')
    missing = tmp_path / 'absent'
    def path(name):
        if name == '/etc/motd':
            if file_state == 'absent': return missing
            if file_state == 'denied': return Mock(read_bytes=Mock(side_effect=PermissionError('denied')))
        if (name, file_state) in (('/etc/hostname', 'hostname-missing'),
                                 ('/etc/machine-id', 'machine-id-missing')):
            return missing
        return witness
    monkeypatch.setattr(__import__('pathlib'), 'Path', path)
    if file_state in ('denied', 'hostname-missing', 'machine-id-missing'):
        with pytest.raises(PermissionError if file_state == 'denied' else FileNotFoundError):
            command.guest_read(PACKAGES)
        return
    value = command.guest_read(PACKAGES)
    assert value['preserved']['files']['/etc/motd'] == (
        None if file_state == 'absent' else hashlib.sha256(witness.read_bytes()).hexdigest())
    assert command.guest_read(PACKAGES) == value
    assert api.resolve.call_count == 240
    raw = (json.dumps(value, sort_keys=True) + '\n').encode()
    assert 16000 < len(raw) < 65536
    item = command.PackageCommand(SimpleNamespace(config={'run': 'owned'}, guard=Mock(),
        call=Mock(return_value=raw)), SimpleNamespace(upgrade_inputs={'packages': PACKAGES}, recheck=Mock()))
    # Freeze the maintained source through its normal constructor/decoder;
    # only the public OS services above are replaced by explicit doubles.
    monkeypatch.setattr(command, 'guest_source', lambda **_: b'fixed source double')
    assert item.read_identity() == value
