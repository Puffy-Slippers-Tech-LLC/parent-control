"""Host-only secret storage and actual Perl helper behavior; no VM or credentials."""

import base64
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
import secret_variables as secret
from private_artifacts import EvidenceError, PrivateCollector
sys.path.pop(0)

CANARY = 'fixture-only-credential-9!'


def test_frozen_registry_stages_private_variables_and_rejects_secret_evidence(tmp_path):
    supplied = {'parent': CANARY, 'child': 'second-fixture-credential-8!'}
    variables = secret.SecretVariables(supplied)
    supplied['parent'] = 'changed-after-registration'
    work = tmp_path / 'work'
    work.mkdir(mode=0o700)
    with PrivateCollector(run_id='secret-test', secrets=variables.registered_secrets,
                          parent=tmp_path) as collector:
        variables.stage(work, {'NOVIDEO': 1})
        path = work / 'vars.json'
        data = json.loads(path.read_bytes())
        assert data == {'NOVIDEO': 1, '_SECRET_ONPC_PARENT_PASSWORD': CANARY,
                        '_SECRET_ONPC_CHILD_PASSWORD': 'second-fixture-credential-8!'}
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert CANARY not in repr(variables)
        for value in variables.registered_secrets:
            for encoded in (value.encode(), base64.b64encode(value.encode())):
                with pytest.raises(EvidenceError, match='secret-detected'):
                    collector.add('unsafe', 'backend', encoded, reviewed=True)
        with pytest.raises(EvidenceError, match='secret-detected'):
            collector.copy(work, 'vars.json', 'vars', 'backend', reviewed=True)
        collector.save_report('result', {'outcome': 'failed', 'code': 'secret:input-failed'})
        collector.verify([])


@pytest.mark.parametrize('passwords', [[], 'unsafe', {'root': CANARY},
    {'parent': ''}, {'parent': None}, {'parent': 123}, {'parent': 'a' * 257},
    {'parent': 'line\nreturn'}, {'parent': 'tab\tvalue'}, {'parent': 'null\0value'},
    {'parent': 'delete\x7f'}, {'parent': 'non-ascii-\u00e9'}, {1: CANARY}])
def test_invalid_registry_refuses_without_exposing_values(passwords):
    with pytest.raises(EvidenceError) as caught:
        secret.SecretVariables(passwords)
    assert str(caught.value) == 'secret:variables'


@pytest.mark.parametrize('key', ['_SECRET_UNREGISTERED', 'ANY_PASSWORD',
                               '_SECRET_ONPC_PARENT_PASSWORD'])
def test_public_variables_cannot_smuggle_unregistered_secrets(tmp_path, key):
    with pytest.raises(EvidenceError, match='variable-collision'):
        secret.SecretVariables().stage(tmp_path, {key: CANARY})
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('kind', ['file', 'symlink', 'hardlink'])
def test_staging_never_overwrites_existing_entries(tmp_path, kind):
    original = tmp_path / 'original'
    original.write_text('preserve')
    path = tmp_path / 'vars.json'
    if kind == 'file':
        path.write_text('preserve')
    elif kind == 'symlink':
        path.symlink_to(original)
    else:
        os.link(original, path)
    with pytest.raises(EvidenceError, match='stage-failed'):
        secret.SecretVariables({'parent': CANARY}).stage(tmp_path, {})
    assert original.read_text() == path.read_text() == 'preserve'


@pytest.mark.parametrize('kind', ['public', 'symlink'])
def test_unsafe_directory_cannot_receive_secrets(tmp_path, kind):
    real = tmp_path / 'real'
    real.mkdir(mode=0o700)
    path = real
    if kind == 'public':
        real.chmod(0o755)
    else:
        path = tmp_path / 'link'
        path.symlink_to(real, target_is_directory=True)
    with pytest.raises((EvidenceError, OSError)):
        secret.SecretVariables({'parent': CANARY}).stage(path, {})
    assert not list(real.iterdir())


def test_replaced_directory_fails_without_writing_to_replacement(tmp_path, monkeypatch):
    work = tmp_path / 'work'
    work.mkdir(mode=0o700)
    moved = tmp_path / 'moved'
    original_open = secret.os.open
    def replace(name, flags, *args, **kwargs):
        if name == 'vars.json':
            work.rename(moved)
            work.mkdir(mode=0o700)
        return original_open(name, flags, *args, **kwargs)
    monkeypatch.setattr(secret.os, 'open', replace)
    with pytest.raises(EvidenceError, match='directory-replaced'):
        secret.SecretVariables({'parent': CANARY}).stage(work, {})
    assert not list(work.iterdir())
    assert stat.S_IMODE((moved / 'vars.json').stat().st_mode) == 0o600


@pytest.mark.parametrize('error', [OSError('private-canary'), KeyboardInterrupt('private-canary')])
def test_interrupted_write_is_private_and_cannot_be_retried(tmp_path, monkeypatch, error):
    def fail(_fd):
        raise error
    monkeypatch.setattr(secret.os, 'fsync', fail)
    variables = secret.SecretVariables({'parent': CANARY})
    with pytest.raises(KeyboardInterrupt if isinstance(error, KeyboardInterrupt) else EvidenceError):
        variables.stage(tmp_path, {})
    assert stat.S_IMODE((tmp_path / 'vars.json').stat().st_mode) == 0o600
    with pytest.raises(EvidenceError, match='stage-failed'):
        variables.stage(tmp_path, {})


# Execute the maintained Perl module with a stub of the PUBLIC testapi only.
# No guest, screenshot, backend, signal delivery or process cleanup is involved.
PERL_PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our ($mode, $role, $surface) = @ARGV;
our @events;
our $canary = 'fixture-only-credential-9!';
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub get_var {
    push @main::events, 'policy';
    return $main::mode eq 'video' ? 0 : 1;
}
sub get_required_var {
    push @main::events, 'variable:' . $_[0];
    die $main::canary if $main::mode eq 'missing';
    return $main::mode eq 'control' ? "unsafe\nvalue" : $main::canary;
}
sub assert_screen {
    push @main::events, 'prompt:' . $_[0];
    die $main::canary if $main::mode eq 'prompt-error';
    return $main::mode eq 'prompt-false' ? 0 : 1;
}
sub type_password {
    die 'wrong password/options' unless @_ == 1 && $_[0] eq $main::canary;
    push @main::events, 'password';
    die $main::canary if $main::mode eq 'typing-error';
    return 1;
}
sub save_screenshot {
    push @main::events, 'capture';
    die $main::canary if $main::mode eq 'capture-error';
    return undef if $main::mode eq 'capture-missing';
    return {screenshot => 'private.png'};
}
package main;
require onpc_password;
my $capture_first = $mode =~ /^capture-/;
my $ok = eval {
    onpc_password::capture_before_authentication() if $capture_first;
    onpc_password::enter_password($role, $surface);
    1;
};
my $error = $ok ? '' : "$@";
my @first = @events;
my $captured = eval { onpc_password::capture_before_authentication(); 1; };
my $capture_error = "$@";
my $retried = eval { onpc_password::enter_password('parent', 'gdm'); 1; };
print encode_json({ok => $ok ? 1 : 0, error => $error, first => \@first,
    events => \@events, captured => $captured ? 1 : 0, capture_error => $capture_error,
    retried => $retried ? 1 : 0});
'''


def probe(mode, role='parent', surface='gdm'):
    result = subprocess.run(['/usr/bin/perl', '-I', str(ROOT / 'tests/integration/graphical_smoke/lib'),
                             '-', mode, role, surface], input=PERL_PROBE, text=True,
                            capture_output=True, timeout=5, check=True)
    assert CANARY not in result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize('role', list(secret.PASSWORD_VARIABLES))
@pytest.mark.parametrize('surface', ['gdm', 'polkit', 'lock'])
def test_password_uses_registered_variable_then_masked_prompt_and_secret_api(role, surface):
    result = probe('success', role, surface)
    assert result['ok'] == 1
    assert result['first'] == ['policy', 'variable:' + secret.PASSWORD_VARIABLES[role],
                               'prompt:onpc-' + surface + '-' + role + '-masked-password', 'password']
    assert result['captured'] == result['retried'] == 0
    assert result['events'] == result['first']


@pytest.mark.parametrize('mode', ['video', 'missing', 'control', 'prompt-error',
                                'prompt-false', 'typing-error', 'capture-error', 'capture-missing'])
def test_password_and_capture_failures_latch_refusal_and_redact_exceptions(mode):
    result = probe(mode)
    assert result['ok'] == result['captured'] == result['retried'] == 0
    assert result['error'] == ('secret:capture-failed\n' if mode.startswith('capture-')
                                else 'secret:input-failed\n')
    assert result['events'] == result['first']
    assert ('password' in result['events']) is (mode == 'typing-error')


@pytest.mark.parametrize('role,surface', [('root', 'gdm'), ('parent', 'terminal'),
                                        ('_SECRET_UNREGISTERED', 'polkit')])
def test_unregistered_credentials_and_unmasked_terminal_refuse_before_any_api(role, surface):
    result = probe('success', role, surface)
    assert result['ok'] == result['retried'] == 0
    assert result['events'] == []


def test_credential_free_capture_works_but_is_closed_before_password_input():
    result = probe('capture-success')
    assert result['ok'] == 1
    assert result['first'][0] == 'capture'
    assert result['events'].count('capture') == 1
    assert result['captured'] == result['retried'] == 0
