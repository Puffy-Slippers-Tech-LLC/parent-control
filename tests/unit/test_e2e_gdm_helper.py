"""Execute maintained GDM helpers against public API successes and refusals."""

import json
from pathlib import Path

import pytest
from tests.support.perl import run_perl

LIB = Path(__file__).resolve().parents[1] / 'integration/graphical_smoke/lib'
PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our $mode = shift;
our $installed = shift;
our @events;
our $screen = 'list';
our $console = 'sut';
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { return $main::mode eq 'wrong-console' ? 'onpc-serial' : $main::console; }
sub assert_screen {
    my ($tag, $timeout) = @_;
    die 'unbounded match' unless $timeout == 90 || $timeout == 30;
    push @main::events, 'match:' . $tag;
    return 0 if $main::mode eq 'missing-list' && $main::screen eq 'list';
    return 0 if $main::mode eq 'missing-prompt' && $main::screen eq 'prompt';
    return 0 if $main::mode eq 'missing-return' && $main::screen eq 'return';
    die 'wrong match' unless $tag eq ($main::screen eq 'prompt'
        ? 'onpc-gdm-parent-masked-password' : $main::screen eq 'return' && $main::installed
        ? 'onpc-gdm-parent-installed-account' : 'onpc-gdm-parent-account');
    return {needle => $tag};
}
sub assert_and_click {
    my ($tag, %opts) = @_;
    die 'unsafe click' unless $tag eq 'onpc-gdm-parent-account'
        && $opts{timeout} == 30 && $opts{mousehide} == 1;
    push @main::events, 'click';
    $main::screen = 'prompt';
}
sub check_screen {
    die 'wrong negative match' unless $_[0] eq 'onpc-gdm-parent-account' && $_[1] == 1;
    push @main::events, 'negative';
    return $main::mode eq 'false-positive';
}
sub send_key {
    die 'unexpected key' unless $_[0] eq 'esc';
    push @main::events, 'escape';
    $main::screen = 'list';
}
sub select_console {
    die 'unexpected console' unless $_[0] eq 'sut';
    push @main::events, 'return';
    $main::screen = 'return';
    $main::console = $_[0];
}
sub record_info { push @main::events, 'record:' . $_[0]; }
sub save_screenshot { die 'explicit capture forbidden'; }
sub type_password { die 'password input forbidden'; }
package main;
require onpc_gdm;
my $ok = eval {
    onpc_gdm::wait_list($mode eq 'deadline' ? 91 : 90);
    onpc_gdm::select_parent();
    onpc_gdm::dismiss_prompt();
    $console = 'onpc-serial' unless $mode eq 'wrong-return-console';
    $installed ? onpc_gdm::return_after_reboot() : onpc_gdm::return_from_serial();
    1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
'''


@pytest.mark.parametrize('mode', ['ok', 'missing-list', 'missing-prompt',
    'false-positive', 'missing-return', 'wrong-console', 'wrong-return-console', 'deadline'])
@pytest.mark.parametrize('installed', [False, True])
def test_screen_readiness_refuses_before_next_action(mode, installed):
    result = run_perl(PROBE, mode, str(int(installed)))
    data = json.loads(result.stdout)
    assert data['ok'] == (mode == 'ok'), data
    events = data['events']
    if mode == 'ok':
        assert events.index('negative') < events.index('escape') < events.index('return')
        assert events[-1] == 'record:gdm-return'
    elif mode in ('missing-list', 'wrong-console', 'deadline'):
        assert 'click' not in events
    elif mode in ('missing-prompt', 'false-positive'):
        assert 'escape' not in events
    elif mode == 'missing-return':
        assert 'record:gdm-return' not in events
    else:
        assert 'return' not in events
