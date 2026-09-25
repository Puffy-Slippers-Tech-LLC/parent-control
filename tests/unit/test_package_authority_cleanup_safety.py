"""Fixed package authority, uncertain-input and public-result regressions."""

import json
import os
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
    install(run, Mock(), command.ARGV[-1])
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
def test_guest_guard_precedes_marker_and_exec(monkeypatch, tmp_path, fault):
    import grp
    import pwd
    control = command.session_control
    monkeypatch.setattr(os, 'geteuid', lambda: 0)
    monkeypatch.setattr(pwd, 'getpwnam', lambda _: SimpleNamespace(
        pw_uid=1000, pw_gid=1000, pw_name='fixture'))
    monkeypatch.setattr(grp, 'getgrnam', lambda _: SimpleNamespace(gr_gid=27))
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
        execute.assert_called_once_with(command.ARGV[0], command.ARGV)
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
