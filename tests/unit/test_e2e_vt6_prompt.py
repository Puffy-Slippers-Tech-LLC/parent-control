"""Credential-free prompt collection: real Perl ordering and controller gates."""

import json
from unittest.mock import Mock

import pytest

import check_graphical_smoke as smoke
from tests.support.perl import run_perl
from tests.support.screens import png


PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our $mode = shift;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub get_var { return $main::mode eq 'video' ? 0 : 1; }
sub select_console { die 'console' unless $_[0] eq 'sut'; }
sub current_console { return $main::mode eq 'console' ? 'onpc-serial' : 'sut'; }
sub send_key { push @main::events, $_[0]; }
sub wait_still_screen { return 1; }
sub type_string {
    die 'input' unless @_ == 3 && $_[0] eq 'onpc-parent-jamie' && $_[1] eq 'secret' && $_[2] == 1;
    push @main::events, 'fixture';
}
sub type_password { die 'password forbidden'; }
sub get_required_var { die 'password access forbidden'; }
sub save_screenshot {
    push @main::events, 'capture';
    die 'private-canary' if $main::mode eq 'capture';
    return {screenshot => 'smoke-1.png'};
}
package main;
require onpc_vt6;
my $exchange = sub {
    my ($stage, $shot) = @_;
    push @events, $stage;
    die 'private-canary' if $mode eq $stage;
    die 'capture shape' unless defined($shot) == ($stage =~ /-screen$/ ? 1 : 0);
    return {vt6_getty_verified => ($mode ne 'getty'),
        vt6_login_process_verified => ($mode ne 'recipient'),
        terminal_echo_disabled => ($mode ne 'echo'), active_vt6_verified => ($mode ne 'inactive')};
};
my $ok = eval { onpc_vt6::inspect_prompt($exchange); 1; };
my $error = $@;
my $retry = eval { onpc_vt6::inspect_prompt($exchange); 1; };
my $capture = eval { onpc_password::capture_before_authentication(); 1; };
print encode_json({ok => $ok ? 1 : 0, error => $error, retry => $retry ? 1 : 0,
                   capture => $capture ? 1 : 0, events => \@events});
'''


@pytest.mark.parametrize('mode', ['ok', 'video', 'console', 'capture', 'getty', 'recipient',
    'echo', 'inactive', 'vt6-ready', 'vt6-login-screen', 'vt6-prompt-ready', 'vt6-prompt-screen'])
def test_prompt_inspection_never_accesses_password_and_latches_failures(mode):
    result = run_perl(PROBE, mode)
    data = json.loads(result.stdout)
    assert 'private-canary' not in result.stdout + result.stderr
    assert data['ok'] == (mode == 'ok')
    assert not data['retry'] and not data['capture']
    if mode == 'ok':
        assert data['events'] == ['ctrl-alt-f6', 'vt6-ready', 'capture', 'vt6-login-screen',
            'fixture', 'ret', 'vt6-prompt-ready', 'capture', 'vt6-prompt-screen']
    if mode in ('video', 'console', 'capture', 'getty', 'inactive', 'vt6-ready', 'vt6-login-screen'):
        assert 'fixture' not in data['events']


@pytest.mark.parametrize('stage', smoke.VT6_PROMPT_STAGES[4:])
@pytest.mark.parametrize('fault', [None, 'boot-before', 'boot-after', 'probe', 'checkpoint', 'capture'])
def test_controller_binds_prompt_capture_to_boot_and_recipient(tmp_path, stage, fault):
    png(tmp_path)
    events = []
    def progress(current, observed):
        assert not (tmp_path / f'{current}.reply.json').exists()
        events.append(observed)
        if fault == 'checkpoint' and observed is not None:
            raise RuntimeError('checkpoint')
    controller = smoke.Smoke(tmp_path, Mock(), Mock(), 'host-key', vt6_prompt=True, progress=progress)
    controller.steps = [{'stage': s} for s in smoke.VT6_PROMPT_STAGES[:smoke.VT6_PROMPT_STAGES.index(stage)]]
    controller._vt6_boot = 'a' * 64
    boots = iter(['b' * 64 if fault == 'boot-before' else 'a' * 64,
                  'b' * 64 if fault == 'boot-after' else 'a' * 64])
    def read(name):
        if name == 'boot':
            return {'boot_sha256': next(boots)}
        assert name == ('vt6-getty' if stage in ('vt6-ready', 'vt6-login-screen') else 'vt6-password')
        if fault == 'probe':
            raise RuntimeError('probe')
        return {'active_vt6_verified': True}
    controller.vm = Mock(read=Mock(side_effect=read))
    capture = 'smoke-1.png' if stage.endswith('-screen') else None
    if fault == 'capture':
        capture = None if capture else 'smoke-1.png'
    (tmp_path / f'{stage}.request.json').write_text(json.dumps({'stage': stage, 'screenshot': capture}))
    if fault:
        with pytest.raises(RuntimeError):
            controller.step()
        assert not (tmp_path / f'{stage}.reply.json').exists()
        with pytest.raises(RuntimeError, match='previous-failure'):
            controller.step()
    else:
        controller.step()
        assert events[-1]['boot_sha256'] == 'a' * 64
        assert (tmp_path / f'{stage}.reply.json').exists()


@pytest.mark.parametrize('options', [{'authenticate': True}, {'serial': True}, {'transfer': Mock()}])
def test_prompt_inspection_cannot_be_combined_with_authentication(tmp_path, options):
    with pytest.raises(RuntimeError, match='vt6-prompt-prerequisites'):
        smoke.Smoke(tmp_path, Mock(), Mock(), 'host-key', vt6_prompt=True, **options)
