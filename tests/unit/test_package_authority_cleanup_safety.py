"""Fixed package authority, uncertain-input and public-result regressions."""

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_e2e_package_authority as check
import check_graphical_smoke as smoke
import package_command as command
from package_authority import PLAN, submit_package
from private_artifacts import EvidenceError
from owned_commands import CommandError
from tests.support.desktop_session import RUN_PROBE, props
from tests.support.package_command import DIGEST, boundary
from tests.support.perl import run_perl


@pytest.fixture(autouse=True)
def platform(monkeypatch):
    monkeypatch.setattr(command.session_control, 'package_format', lambda: 'deb')


def test_fixed_launcher(monkeypatch):
    launch = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', launch)
    assert check.main() == 0
    launch.assert_called_once_with(assets=check.ASSETS, provision_credentials=True,
                                  package_authority=True)


def test_package_install_allows_dependencies_on_product_free_baseline(monkeypatch):
    # The empty baseline need not have runtime dependencies installed/cached.
    # Keep the public install arguments aligned with the maintained setup recipe.
    from guest_install_recipe import install
    monkeypatch.setenv('DEBIAN_FRONTEND', 'noninteractive')
    run = Mock()
    install(run, Mock(), Path(command.ARGV[-1]))
    expected = run.call_args_list[-1].args[0]
    assert command.ARGV[0] == '/usr/bin/' + expected[0]
    assert command.ARGV[1:] == tuple(expected[1:])


@pytest.mark.parametrize('extra', [{}, {'install': True}, {'product_free_entry': True},
                                  {'challenges': True}, {'fresh_desktop': 'parent'}])
def test_launcher_requires_exclusive_product_free_mode(extra):
    kwargs = dict(assets=check.ASSETS, provision_credentials=True, **extra) if extra else {}
    with pytest.raises(CommandError):
        smoke.main(package_authority=True, **kwargs)


@pytest.mark.parametrize('fault', ['binding', 'digest', 'vm', 'attempt', 'transport', 'provenance'])
def test_bad_input_never_submits(monkeypatch, fault):
    item = boundary(monkeypatch)
    binding, digest, identity = command.BINDING, DIGEST, dict(item.identity)
    if fault == 'binding': binding = 'shell'
    if fault == 'digest': digest = 'b' * 64
    if fault == 'vm': identity['domain_uuid'] = 'another'
    if fault == 'attempt': identity['run'] = 'another'
    if fault == 'transport': item.transport.config['run'] = 'another'
    if fault == 'provenance': item.verified.recheck.side_effect = EvidenceError('changed')
    with pytest.raises(EvidenceError): item.submit(binding, digest, identity)
    item.transport.call.assert_not_called()
    command.session_control.observe.assert_not_called()


@pytest.mark.parametrize('fault', ['transport', 'timeout', 'output', 'success'])
def test_uncertain_submission_cannot_replay(monkeypatch, fault):
    item = boundary(monkeypatch)
    if fault == 'transport': item.transport.call.side_effect = RuntimeError('lost')
    if fault == 'timeout': item.transport.call.side_effect = TimeoutError()
    if fault == 'output':
        item.transport.call.side_effect = lambda *a, **kw: kw['on_output'](b'x' * (command.LIMIT + 1))
    if fault == 'success':
        assert item.submit(command.BINDING, DIGEST, item.identity) == {'submitted': True}
    else:
        with pytest.raises((RuntimeError, TimeoutError, EvidenceError)):
            item.submit(command.BINDING, DIGEST, item.identity)
    with pytest.raises(EvidenceError, match='package:replay'):
        item.submit(command.BINDING, DIGEST, item.identity)
    assert item.transport.call.call_count == 1


@pytest.mark.parametrize('fault', ['', 'missing', 'status', 'echo', 'trailing', 'completion',
                                   'bound', 'owner', 'provenance'])
def test_independent_readback_requires_actual_success_and_final_notice(monkeypatch, fault):
    item = boundary(monkeypatch)
    if fault != 'missing': item.submit(command.BINDING, DIGEST, item.identity)
    if fault == 'status': item.receipt = (item.receipt[0], 1)
    if fault == 'echo': item.receipt = (b'echo ' + command.NOTICE.encode(), 0)
    if fault == 'trailing': item.receipt = (item.receipt[0] + b'later output\n', 0)
    if fault == 'completion': item.receipt = (command.NOTICE.encode(), 0)
    if fault == 'bound': item.receipt = (b'x' * (command.LIMIT + 1), 0)
    if fault == 'owner': item.transport.guard.side_effect = EvidenceError('changed')
    if fault == 'provenance': item.verified.recheck.side_effect = EvidenceError('changed')
    if fault:
        with pytest.raises(EvidenceError): item.read_result()
    else:
        result = item.read_result()
        assert result['notice'] == command.NOTICE and result['completion'] == command.COMPLETE
        assert result['exit_status'] == 0
        item.transport.guard.assert_called_once_with(item.identity)


def test_qualification_refuses_wrong_inputs_then_submits_once(monkeypatch):
    item = boundary(monkeypatch)
    journey = SimpleNamespace(transport=item.transport,
                              context=SimpleNamespace(verified=item.verified))
    result = submit_package(journey, Mock())
    assert result['refusals'] == ['unregistered', 'artifact', 'vm', 'attempt', 'replay']
    assert item.transport.call.call_count == 1


@pytest.mark.parametrize('fault', ['', 'binding', 'authority', 'owner', 'digest', 'changed', 'replay'])
@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_guest_guard_precedes_marker_and_exec(monkeypatch, tmp_path, fault, package_format):
    import grp
    import pwd
    control = command.session_control
    monkeypatch.setattr(control, 'package_format', lambda: package_format)
    monkeypatch.setattr(os, 'geteuid', lambda: 0)
    monkeypatch.setattr(pwd, 'getpwnam', lambda _: SimpleNamespace(
        pw_uid=1000, pw_gid=1000, pw_name='fixture'))
    def group(name):
        assert name == ('wheel' if package_format == 'rpm' else 'sudo')
        return SimpleNamespace(gr_gid=27)
    monkeypatch.setattr(grp, 'getgrnam', group)
    monkeypatch.setattr(os, 'getgrouplist', lambda *_: [] if fault == 'authority' else [27])
    monkeypatch.setattr(control, 'sessions', Mock(side_effect=[
        {'7': props('1001' if fault == 'owner' else '1000')},
        {'8' if fault == 'changed' else '7': props()}]))
    monkeypatch.setattr(control, 'package_digest', lambda: 'b' * 64 if fault == 'digest' else DIGEST)
    marker = tmp_path / 'used'
    if fault == 'replay': marker.touch()
    opening = os.open
    calls = []
    def open_marker(path, flags, mode):
        calls.append(path)
        assert path == '/var/lib/onpc-e2e-assets/.package-install-used'
        return opening(marker, flags, mode)
    monkeypatch.setattr(os, 'open', open_marker)
    monkeypatch.setattr(os, 'environ', {})
    monkeypatch.setattr(os, 'dup2', Mock())
    execute = Mock()
    monkeypatch.setattr(os, 'execv', execute)
    if fault:
        with pytest.raises((control.SessionError, FileExistsError)):
            command.guest_submit('invalid' if fault == 'binding' else command.BINDING, DIGEST)
        execute.assert_not_called()
        assert bool(calls) == (fault == 'replay')
    else:
        command.guest_submit(command.BINDING, DIGEST)
        argv = (('/usr/bin/dnf', '--quiet', 'install', '-y',
                 '/var/lib/onpc-e2e-assets/package.rpm') if package_format == 'rpm' else command.ARGV)
        execute.assert_called_once_with(argv[0], argv)
        with pytest.raises(FileExistsError):
            # A new process uses the same exclusive marker, independent of the
            # controller's in-memory attempted flag.
            control.sessions.side_effect = None
            control.sessions.return_value = {'7': props()}
            command.guest_submit(command.BINDING, DIGEST)
        assert execute.call_count == 1


def test_guest_source_is_complete_and_uses_shared_reader():
    source = command.guest_source()
    compile(source, '<package-command>', 'exec')
    assert b'def package_digest' in source


@pytest.mark.parametrize('fault', ['', 'identity', 'version', 'repository', 'payload',
    'script', 'symlink', 'mode', 'extra-script', 'livepatch', 'product', 'preexisting', 'missing-request'])
@pytest.mark.parametrize('entry', [True, False])
def test_unrelated_read_binds_distribution_bytes_and_genuine_request(monkeypatch, fault, entry):
    import hashlib
    import pathlib
    import stat
    import subprocess
    import installation_observations as observations
    expected = dict(observations.UNRELATED_PACKAGE)
    script = b'verified-maintainer-script'
    digests = {path: hashlib.sha256(script).hexdigest() for path in observations.UNRELATED_SCRIPTS}
    monkeypatch.setattr(observations, 'UNRELATED_SCRIPTS', digests)
    installed = [expected['name'], 'wrong' if fault == 'version' else expected['version'],
                 expected['architecture'], 'install ok installed']
    repository = '\n'.join(field + ': ' + ('wrong' if fault == 'repository' and key == 'sha256'
        else expected[key]) for field, key in (('Package', 'name'), ('Version', 'version'),
        ('Architecture', 'architecture'), ('SHA256', 'sha256'), ('Filename', 'filename'),
        ('Origin', 'origin'), ('Source', 'source')))
    def run(argv, **kwargs):
        assert kwargs['timeout'] == 30 and kwargs['capture_output']
        output = ('\n'.join(installed) + '\n' if argv[0] == '/usr/bin/dpkg-query' else
                  repository if argv[0] == '/usr/bin/apt-cache' else
                  'changed payload' if fault == 'payload' else '')
        return SimpleNamespace(returncode=0, stdout=output.encode())
    query = Mock(side_effect=run)
    monkeypatch.setattr(subprocess, 'run', query)
    request = (not entry and fault != 'missing-request') or (entry and fault == 'preexisting')
    def exists(path):
        return (path in ('/run/reboot-required', '/run/reboot-required.pkgs') and request
                or path.endswith('.config') and fault == 'extra-script'
                or path == '/snap/bin/canonical-livepatch' and fault == 'livepatch'
                or path == '/run/oh-no-parent-control-child-trust-reboot' and fault == 'product')
    monkeypatch.setattr(os.path, 'lexists', exists)
    monkeypatch.setattr(os, 'access', lambda *_: True)
    def node(path):
        item = Mock()
        item.resolve.return_value = object() if fault == 'symlink' else item
        item.lstat.return_value = SimpleNamespace(st_mode=stat.S_IFREG | (
            0o777 if fault == 'mode' else 0o755), st_uid=0, st_gid=0, st_nlink=1, st_size=42)
        item.read_bytes.return_value = b'changed' if fault == 'script' else script
        item.read_text.return_value = ('*** System restart required ***\n' if path == '/run/reboot-required'
            else 'libc6\n' + ('oh-no-parent-control\n' if fault == 'product' else ''))
        return item
    monkeypatch.setattr(pathlib, 'Path', node)
    if fault == 'identity': expected['sha256'] = '0' * 64
    applicable = fault and (fault != 'preexisting' or entry) and (fault != 'missing-request' or not entry)
    if applicable:
        with pytest.raises(command.session_control.SessionError):
            observations.unrelated_observation(expected, entry=entry)
    else:
        value = observations.unrelated_observation(expected, entry=entry)
        assert value['system_reboot_required'] is (not entry)
        assert value['request_packages'] == ([] if entry else ['libc6'])
        assert value['package'] == observations.UNRELATED_PACKAGE
    if fault == 'identity': query.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'identity', 'context', 'digest', 'entry', 'replay'])
def test_unrelated_guest_guard_consumes_once_before_normal_reconfiguration(monkeypatch, tmp_path, fault):
    import grp
    import pwd
    control = command.session_control
    monkeypatch.setattr(os, 'geteuid', lambda: 0)
    monkeypatch.setattr(pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name='fixture'))
    monkeypatch.setattr(grp, 'getgrnam', lambda _: SimpleNamespace(gr_gid=27))
    monkeypatch.setattr(os, 'getgrouplist', lambda *_: [27])
    monkeypatch.setattr(control, 'sessions', lambda: {'7': props('1001' if fault == 'context' else '1000')})
    item = {'version': 'current', 'sha256': DIGEST}
    packages = {'current': item, 'unrelated': dict(command.UNRELATED_PACKAGE)}
    if fault == 'identity': packages['unrelated']['version'] = 'wrong'
    def entry(expected, **kwargs):
        control.require(expected == command.UNRELATED_PACKAGE, 'unrelated-package:identity')
        control.require(fault != 'entry', 'unrelated-package:preexisting-request')
    monkeypatch.setattr(command, 'unrelated_observation', Mock(side_effect=entry))
    monkeypatch.setattr(command, 'guest_read', lambda _: {'version': item['version'], 'packages': {'current': DIGEST}})
    marker = tmp_path / 'used'
    if fault == 'replay': marker.touch()
    opening = os.open
    def consume(path, flags, mode):
        assert path == '/var/lib/onpc-e2e-assets/.package-unrelated-reconfigure-used'
        return opening(marker, flags, mode)
    monkeypatch.setattr(os, 'open', consume)
    monkeypatch.setattr(os, 'environ', {})
    monkeypatch.setattr(os, 'dup2', Mock())
    execute = Mock()
    monkeypatch.setattr(os, 'execv', execute)
    if fault:
        with pytest.raises((control.SessionError, FileExistsError)):
            command.guest_submit(command.UNRELATED, '0' * 64 if fault == 'digest' else
                                 command.UNRELATED_PACKAGE['sha256'], packages)
        execute.assert_not_called()
        assert marker.exists() is (fault == 'replay')
    else:
        command.guest_submit(command.UNRELATED, command.UNRELATED_PACKAGE['sha256'], packages)
        execute.assert_called_once_with(command.UNRELATED_ARGV[0], command.UNRELATED_ARGV)
        with pytest.raises(FileExistsError):
            command.guest_submit(command.UNRELATED, command.UNRELATED_PACKAGE['sha256'], packages)
        assert execute.call_count == 1


def test_unrelated_guest_bundle_refuses_before_os_access(tmp_path):
    import subprocess
    result = subprocess.run(['/usr/bin/python3', '-I', '-', 'invalid', '0' * 64],
        input=command.guest_source(), cwd=tmp_path, capture_output=True, timeout=10)
    assert result.returncode != 0 and b'session:package-binding' in result.stderr
    assert b'ModuleNotFoundError' not in result.stderr


@pytest.mark.parametrize('fault', ['', 'status', 'echo', 'product', 'owner', 'obsolete',
                                  'empty', 'duplicate', 'wrong-trigger', 'malformed'])
def test_unrelated_completion_is_separate_from_system_request(monkeypatch, fault):
    item = boundary(monkeypatch)
    item.binding = command.UNRELATED
    completed = b'Processing triggers for systemd (259.5-0ubuntu3.4) ...\n'
    raw = completed
    if fault == 'echo': raw = b'echo ' + completed
    if fault == 'product': raw += command.NOTICE.encode() + b'\n'
    if fault == 'obsolete': raw = b'Nothing to restart.\n'
    if fault == 'empty': raw = b''
    if fault == 'duplicate': raw += completed
    if fault == 'wrong-trigger': raw = completed.replace(b'systemd', b'libc-bin')
    if fault == 'malformed': raw = completed.replace(b'259.5-0ubuntu3.4', b'not a version')
    item.receipt = (raw, 1 if fault == 'status' else 0)
    if fault == 'owner': item.transport.guard.side_effect = EvidenceError('wrong-owner')
    if fault:
        with pytest.raises(EvidenceError): item.read_result()
    else:
        value = item.read_result()
        assert value['completion'] == completed.decode().strip() and value['notice'] is None
        assert 'system_reboot_required' not in value
    item.transport.call.assert_not_called()


@pytest.mark.parametrize('entry', [True, False])
@pytest.mark.parametrize('fault', ['', 'identity', 'request', 'product', 'bound', 'owner'])
def test_unrelated_controller_decodes_real_shape_and_freezes_complete_payload(monkeypatch, entry, fault):
    item = boundary(monkeypatch)
    value = {'package': dict(command.UNRELATED_PACKAGE), 'integration_verified': True,
        'system_reboot_required': not entry, 'request_packages': [] if entry else ['libc6'],
        'message': None if entry else '*** System restart required ***', 'product_request_absent': True}
    if fault == 'identity': value['package']['architecture'] = 'i386'
    if fault == 'request': value['system_reboot_required'] = entry
    if fault == 'product': value['product_request_absent'] = False
    raw = (json.dumps(value, sort_keys=True) + '\n').encode()
    if fault == 'bound': raw = b'x' * 65537
    item.transport.call.return_value = raw
    if fault == 'owner': item.transport.guard.side_effect = EvidenceError('wrong-owner')
    if fault:
        with pytest.raises(EvidenceError): item.read_unrelated(entry=entry)
    else:
        assert item.read_unrelated(entry=entry) == value
    if fault != 'owner':
        payload = item.transport.call.call_args.kwargs['input']
        compile(payload, '<unrelated-read>', 'exec')
        assert b'def unrelated_observation' in payload and b'import json' in payload
        assert b'guest_submit(sys.argv' not in payload


@pytest.mark.parametrize('fault', ['', 'phase', 'entry', 'transport', 'digest', 'attempt'])
def test_unrelated_controller_uses_guarded_command_and_retains_uncertainty(monkeypatch, fault):
    item = boundary(monkeypatch)
    identity = {'version': 'wrong' if fault == 'phase' else 'current'}
    item.read_identity = Mock(return_value=identity)
    item.package_identities = Mock(return_value={'current': {'version': 'current'}})
    item.read_unrelated = Mock(side_effect=EvidenceError('preexisting-request') if fault == 'entry' else None)
    if fault == 'transport': item.transport.call.side_effect = TimeoutError()
    digest = '0' * 64 if fault == 'digest' else command.UNRELATED_PACKAGE['sha256']
    owner = {**item.identity, 'run': 'wrong-attempt'} if fault == 'attempt' else item.identity
    if fault:
        with pytest.raises((EvidenceError, TimeoutError)): item.submit(command.UNRELATED, digest, owner)
    else:
        assert item.submit(command.UNRELATED, digest, owner) == {'submitted': True}
        args = item.transport.call.call_args.args[0]
        assert args[:3] == ['/usr/bin/python3', '-I', '-'] and args[3] == command.UNRELATED
        assert json.loads(args[-1])['unrelated'] == command.UNRELATED_PACKAGE
    if fault in ('', 'transport'):
        with pytest.raises(EvidenceError, match='replay'):
            item.submit(command.UNRELATED, command.UNRELATED_PACKAGE['sha256'], item.identity)
        assert item.transport.call.call_count == 1
    else:
        item.transport.call.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'version', 'query'])
def test_fedora_completion_also_requires_independent_exact_installed_identity(monkeypatch, fault):
    item = boundary(monkeypatch)
    item.verified.asset_files = {'package.rpm': DIGEST}
    item.receipt = (('>>> Running %posttrans scriptlet: oh-no-parent-control-0:1.3-1.fc44.x86_64\n'
        '>>> Finished %posttrans scriptlet: oh-no-parent-control-0:1.3-1.fc44.x86_64\n'
        '>>> Scriptlet output:\n>>> ' + command.COMPLETE + '\n>>> ' + command.NOTICE + '\n>>> \n'
        'Warning: skipped OpenPGP checks for 1 package from repository: @commandline\n').encode(), 0)
    item.binding = command.BINDING
    item.read_identity = Mock(return_value={'version': 'wrong' if fault == 'version' else '0:1.3-1.fc44'},
        side_effect=EvidenceError('package:command-failed') if fault == 'query' else None)
    item.package_identities = Mock(return_value={'current': {'name': 'oh-no-parent-control',
        'version': '0:1.3-1.fc44', 'architecture': 'x86_64'}})
    if fault:
        with pytest.raises(EvidenceError):
            item.read_result()
    else:
        assert item.read_result()['notice'] == command.NOTICE
    item.read_identity.assert_called_once_with()


@pytest.mark.parametrize('fault', ['', 'command-context', 'package-submitted', 'package-result'])
def test_worker_stops_at_uncertain_checkpoint(fault):
    source = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_package_authority;')
    source = source.replace('onpc_desktop_session::run', 'onpc_package_authority::run')
    source = source.replace('}, $action);', '});')
    source = source.replace("push @events, ['stage', $_[0]];",
        "push @events, ['stage', $_[0]]; die 'fixed failure' if $_[0] eq $action;")
    result = json.loads(run_perl(source, fault).stdout)
    assert bool(result['ok']) == (not fault)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(PLAN.screen_tags)
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    if not fault: assert result['events'][-1] == ['power', 'off']
