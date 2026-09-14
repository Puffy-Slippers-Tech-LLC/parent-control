"""Synthetic journal correlation; no daemon or activation qualification."""

from dataclasses import replace
import hashlib

import pytest

from oh_no_parent_control.execution_probe import ProbeResult
from oh_no_parent_control.probe_channel import AdmissionBinding, PeerHello
from oh_no_parent_control.probe_generation import GenerationIdentity
from system_probe_decision import (
    BackendInputs, DecisionRefused, SYSLOG_FORMAT, bind_positive_decision,
)


@pytest.fixture
def observation():
    token = 'a' * 32
    directory = f'/run/oh-no-parent-control/probes/{token}'
    generation = GenerationIdentity(token, directory, f'{directory}/witness', 1, 2, 'b' * 64, 200)
    binding = AdmissionBinding(PeerHello(1234, 0, 0, 'c' * 32), ':1.2',
                               f'onpc-execution-probe-{token}.service',
                               '/org/freedesktop/systemd1/job/17')
    probe = ProbeResult(
        unit=binding.unit, manager=binding.manager, job=binding.job,
        create_outcome='replied', invocation=binding.peer.invocation,
        outcome='identity-unproven', service_result='exit-code', exit_code=1, exit_status=23,
        terminal_observed=True, reference_released=True, client_closed=True, cleanup_complete=True,
        generation=generation, admission=binding, channel_result='executed', native_verified=True,
        job_timeout_usec=4_000_000)
    compiled = ('# controlled fixture\n\n'
                'deny_syslog perm=execute uid=1001 : path=/opt/fixture/blocked\n'
                '# comments do not consume rule numbers\n'
                f'allow_syslog perm=execute uid=0 : path={generation.witness}\n'
                'allow perm=execute all : all\n').encode()
    backend = BackendInputs('d' * 32, 'e' * 32, 321, 'f' * 64, compiled,
                            f'permissive = 0\nsyslog_format = {SYSLOG_FORMAT}\n'.encode(),
                            'active', False)
    entry = {
        '_BOOT_ID': backend.boot, '_SYSTEMD_INVOCATION_ID': backend.invocation,
        '_PID': str(backend.pid), '_UID': '0', '_EXE': '/usr/sbin/fapolicyd',
        '_SYSTEMD_UNIT': 'fapolicyd.service', '_TRANSPORT': 'syslog',
        '__MONOTONIC_TIMESTAMP': '110', '__CURSOR': 's=local;i=17',
        'MESSAGE': f'rule=2 dec=allow_syslog perm=execute pid=1234 uid=0 : path={generation.witness}',
    }
    return dict(entry=entry, before=backend, after=backend, probe=probe,
                start_usec=100, end_usec=120)


def test_positive_observation_binds_inputs_without_promoting_probe(observation):
    result = bind_positive_decision(**observation)
    assert result.generation == observation['probe'].generation.token
    assert result.compiled_sha256 == hashlib.sha256(observation['before'].compiled).hexdigest()
    assert result.config_sha256 == hashlib.sha256(observation['before'].config).hexdigest()
    assert result.daemon_invocation == observation['before'].invocation
    assert result.daemon_pid != result.peer_pid
    assert result.probe_invocation == observation['probe'].invocation
    assert result.rule_number == 2
    assert not observation['probe'].executed
    assert not hasattr(result, 'activated')


@pytest.mark.parametrize('field,value', [
    ('boot', '1' * 32), ('invocation', '2' * 32), ('pid', 322),
    ('executable_sha256', '3' * 64), ('compiled', b'allow perm=execute all : all\n'),
    ('config', b'permissive = 1\n'), ('active_state', 'inactive'),
    ('legacy_rules_present', True),
])
def test_restart_or_changed_input_invalidates_observation(observation, field, value):
    observation['after'] = replace(observation['after'], **{field: value})
    with pytest.raises(DecisionRefused, match='backend-input-changed'):
        bind_positive_decision(**observation)


@pytest.mark.parametrize('field,value', [
    ('boot', ''), ('invocation', '0' * 32), ('pid', True), ('pid', 0),
    ('executable_sha256', ''), ('active_state', 'inactive'), ('legacy_rules_present', True),
    ('config', b'permissive = 1\n'), ('config', b''),
])
def test_matching_but_unqualified_backend_is_refused(observation, field, value):
    observation['before'] = observation['after'] = replace(observation['before'], **{field: value})
    with pytest.raises(DecisionRefused, match='backend-'):
        bind_positive_decision(**observation)


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'bad-format', 'binary'])
def test_config_requires_explicit_unambiguous_nonpermissive_logging(observation, change):
    config = observation['before'].config
    if change == 'missing':
        config = config.replace(b'permissive = 0\n', b'')
    elif change == 'duplicate':
        config += b'permissive = 0\n'
    elif change == 'bad-format':
        config = config.replace(b'pid,uid', b'auid,pid')
    else:
        config += b'\xff'
    observation['before'] = observation['after'] = replace(observation['before'], config=config)
    with pytest.raises(DecisionRefused, match='backend-config-'):
        bind_positive_decision(**observation)


@pytest.mark.parametrize('field,value', [
    ('_BOOT_ID', '1' * 32), ('_SYSTEMD_INVOCATION_ID', '2' * 32), ('_PID', '1234'),
    ('_UID', '1001'), ('_EXE', '/usr/bin/logger'), ('_SYSTEMD_UNIT', 'foreign.service'),
    ('_TRANSPORT', 'stdout'), ('_PID', ['321', '321']), ('_BOOT_ID', None),
    ('__MONOTONIC_TIMESTAMP', '99'), ('__MONOTONIC_TIMESTAMP', '121'),
    ('__MONOTONIC_TIMESTAMP', ['110']), ('__CURSOR', ''), ('__CURSOR', ['cursor']),
])
def test_untrusted_stale_or_ambiguous_journal_fields_refuse(observation, field, value):
    observation['entry'][field] = value
    # User-supplied syslog fields cannot substitute for trusted metadata.
    observation['entry'].update(SYSLOG_PID='321', SYSLOG_IDENTIFIER='fapolicyd',
                                INVOCATION_ID='e' * 32)
    with pytest.raises(DecisionRefused, match='journal-'):
        bind_positive_decision(**observation)


@pytest.mark.parametrize('old,new', [
    ('rule=2', 'rule=1'), ('pid=1234', 'pid=999'), ('uid=0', 'uid=1001'),
    ('allow_syslog', 'deny_syslog'), ('allow_syslog', 'allow'), ('execute', 'open'),
    ('a' * 32, '9' * 32), ('rule=2', 'rule=2 rule=2'), ('path=', 'path=?'),
])
def test_foreign_rule_subject_generation_or_decision_refuses(observation, old, new):
    observation['entry']['MESSAGE'] = observation['entry']['MESSAGE'].replace(old, new)
    with pytest.raises(DecisionRefused, match='decision-'):
        bind_positive_decision(**observation)


@pytest.mark.parametrize('message', [None, [], 'Ruleset identity: ' + 'f' * 64,
                                    'x' * 512, 'rule=2 dec=allow_syslog'])
def test_missing_truncated_or_digest_only_message_is_not_a_decision(observation, message):
    observation['entry']['MESSAGE'] = message
    with pytest.raises(DecisionRefused, match='decision-message-invalid'):
        bind_positive_decision(**observation)


@pytest.mark.parametrize('field,value', [
    ('generation', None), ('admission', None), ('native_verified', False),
    ('terminal_observed', False), ('cleanup_complete', False), ('client_closed', False),
    ('reference_released', False), ('create_outcome', 'uncertain'),
    ('outcome', 'execution-failed'), ('channel_result', 'exec-failed'),
    ('exit_code', 2), ('exit_status', 203), ('service_result', 'timeout'), ('job_timeout_usec', 0),
    ('invocation', '1' * 32), ('manager', ':1.999'), ('unit', 'foreign.service'),
    ('job', '/org/freedesktop/systemd1/job/99'),
])
def test_incomplete_or_mismatched_native_evidence_refuses(observation, field, value):
    observation['probe'] = replace(observation['probe'], **{field: value})
    with pytest.raises(DecisionRefused, match='native-'):
        bind_positive_decision(**observation)


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'set', 'malformed', 'binary'])
def test_compiled_binding_rejects_missing_marker_or_unqualified_grammar(observation, change):
    compiled = observation['before'].compiled
    marker = f'allow_syslog perm=execute uid=0 : path={observation["probe"].generation.witness}\n'.encode()
    if change == 'missing':
        compiled = compiled.replace(marker, b'')
    elif change == 'duplicate':
        compiled += marker
    elif change == 'set':
        compiled = b'%uids=1001,1002\n' + compiled
    elif change == 'malformed':
        compiled += b'invalid after the marker\n'
    else:
        compiled += b'\xff\n'
    observation['before'] = observation['after'] = replace(observation['before'], compiled=compiled)
    with pytest.raises(DecisionRefused, match='compiled-|generation-rule-'):
        bind_positive_decision(**observation)


@pytest.mark.parametrize('field,value', [
    ('token', '0' * 32), ('directory', '/tmp/foreign'), ('witness', '/tmp/foreign'),
    ('sha256', 'invalid'),
])
def test_generation_coordinates_cannot_be_substituted(observation, field, value):
    generation = replace(observation['probe'].generation, **{field: value})
    observation['probe'] = replace(observation['probe'], generation=generation)
    with pytest.raises(DecisionRefused, match='generation-identity-invalid'):
        bind_positive_decision(**observation)


@pytest.mark.parametrize('start,end', [(110, 110), (120, 100), (-1, 120), (True, 120)])
def test_invalid_observation_window_refuses(observation, start, end):
    observation.update(start_usec=start, end_usec=end)
    with pytest.raises(DecisionRefused, match='observation-window-invalid'):
        bind_positive_decision(**observation)


def test_refusal_does_not_echo_private_journal_payload(observation):
    observation['entry']['MESSAGE'] = 'private fixture payload'
    with pytest.raises(DecisionRefused) as error:
        bind_positive_decision(**observation)
    assert str(error.value) == 'decision-message-invalid'
