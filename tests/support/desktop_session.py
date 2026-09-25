"""Shared synthetic session properties and graphical worker probe."""


def props(uid='1000', *, active='yes', locked='no', kind='user', remote='no', seat='seat0'):
    return {'User': uid, 'Active': active, 'LockedHint': locked, 'Class': kind,
            'Remote': remote, 'Seat': seat, 'Type': 'wayland'}


RUN_PROBE = r'''
use strict;
use warnings;
use JSON::PP;
our $action = $ARGV[0];
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub reset_consoles { }
sub select_console { }
sub get_var { $_[0] eq 'NOVIDEO' ? '1' : $_[1] }
sub get_required_var { 'unit-fixture-value' }
sub type_password { push @main::events, ['secret']; }
sub type_string { push @main::events, ['text', $_[0]]; }
sub send_key { push @main::events, ['key', $_[0]]; }
sub save_screenshot { die 'explicit capture forbidden'; }
sub record_info { }
sub mouse_set { push @main::events, ['pointer', @_]; }
sub mouse_click { push @main::events, ['click', $_[0] // 'left']; }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', $_[0]]; }
sub check_shutdown { 1 }
package Console;
sub disable { }
sub mouse_width { 1280 }
sub mouse_height { 800 }
package main;
require onpc_desktop_session;
my $ok = eval {
    onpc_desktop_session::run(sub {
        push @events, ['stage', $_[0]];
        return {observed => $_[0]} if $_[0] =~ /recipient-(?:qualified|rechecked)\z/;
        return {ui_focused => 1} if $_[0] =~ /(?:greeter|list)$/;
        return {observed => $_[0]};
    }, $action);
    1;
};
print encode_json({ok => $ok ? 1 : 0, events => \@events});
'''
