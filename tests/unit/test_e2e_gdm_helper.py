"""Execute maintained GDM helpers against public API successes and refusals."""

import json
from pathlib import Path

import pytest
from tests.support.perl import run_perl

LIB = Path(__file__).resolve().parents[1] / 'integration/graphical_smoke/lib'

INSTALLED_INPUT = r'''
use strict;
use warnings;
use JSON::PP;
our $mode = shift;
our $clicked = 0;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { $main::mode eq 'wrong-console' ? 'onpc-serial' : 'sut' }
sub assert_and_click {
    my ($tag, %opts) = @_;
    die 'wrong tag' unless $tag eq 'onpc-gdm-parent-installed-input-account'
        && $opts{timeout} == 30 && $opts{mousehide} == 1;
    die 'missing account' if $main::mode eq 'missing-account';
    $main::clicked = 1;
}
sub wait_still_screen { die 'unbounded wait' unless $_[0] == 1 && $_[1] == 10; }
sub check_screen {
    die 'wrong negative' unless $_[0] eq 'onpc-gdm-parent-installed-account' && $_[1] == 1;
    return $main::mode eq 'still-list';
}
sub type_password { die 'secret forbidden'; }
package main;
require onpc_gdm;
my $ok = eval { onpc_gdm::inspect_installed_parent(); 1; };
print encode_json({ok => $ok ? 1 : 0, clicked => $clicked});
'''


@pytest.mark.parametrize('mode', ['ok', 'wrong-console', 'missing-account', 'still-list'])
def test_installed_selection_requires_reviewed_input_and_leaves_the_list(mode):
    result = json.loads(run_perl(INSTALLED_INPUT, mode).stdout)
    assert result['ok'] == (mode == 'ok')
    assert result['clicked'] == (mode in ('ok', 'still-list'))

REATTACH = r'''
use strict;
use warnings;
use JSON::PP;
our $mode = shift;
our $activated = 1;
our $connected = 0;
our $matched = 0;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { $main::mode eq 'wrong-console' ? 'onpc-serial' : 'sut' }
sub reset_consoles { $main::activated = 0; }
sub select_console {
    die 'wrong console' unless $_[0] eq 'sut';
    if (!$main::activated) { $main::connected = 1; $main::activated = 1; }
}
sub assert_screen {
    die 'stale screen' unless $main::connected;
    die 'wrong match' unless $_[0] eq 'onpc-gdm-parent-installed-account' && $_[1] == 90;
    return 0 if $main::mode eq 'missing-list';
    $main::matched = 1;
    return 1;
}
sub type_password { die 'secret forbidden'; }
sub assert_and_click { die 'input forbidden'; }
package main;
require onpc_gdm;
my $ok = eval { onpc_gdm::reattach_after_setup(); 1; };
print encode_json({ok => $ok ? 1 : 0, connected => $connected, matched => $matched});
'''


@pytest.mark.parametrize('mode', ['ok', 'wrong-console', 'missing-list'])
def test_setup_reattachment_requires_fresh_connection_and_match(mode):
    result = json.loads(run_perl(REATTACH, mode).stdout)
    assert result['ok'] == result['matched'] == (mode == 'ok')
    assert result['connected'] == (mode != 'wrong-console')


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
@pytest.mark.parametrize('failure', ['', 'gdm', 'focused', 'selected', 'dismissed'])
def test_functional_greeter_uses_normal_keys_and_stops_on_failed_observation(failure):
    probe = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
our $failure = shift;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub send_key { push @main::events, 'key:' . $_[0]; }
sub record_info { }
sub assert_screen { die 'pixels forbidden'; }
sub save_screenshot { die 'capture forbidden'; }
package main;
require onpc_gdm;
require onpc_journey;
my $journey = onpc_journey->new(prefix => 'smokeui', review => 0, exchange => sub {
    push @events, $_[0];
    die 'unavailable' if $_[0] eq $failure;
    return {ui_keys => ['home', 'down']};
});
my $ok = eval { onpc_gdm::functional_selection($journey); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''
    data = json.loads(run_perl(probe, failure).stdout)
    expected = ['gdm', 'key:home', 'key:down', 'focused', 'key:ret', 'selected', 'key:esc', 'dismissed']
    assert data['ok'] == (not failure)
    assert data['events'] == (expected[:expected.index(failure) + 1] if failure else expected)
